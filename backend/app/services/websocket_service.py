from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
import logging
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger("foodbridge.websocket")


@dataclass
class ConnectionInfo:
    user_id: Optional[str] = None
    donation_id: Optional[str] = None
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: Optional[datetime] = None
    message_count: int = 0


active_connections: List[WebSocket] = []
donation_rooms: Dict[str, List[WebSocket]] = {}
connection_metadata: Dict[int, ConnectionInfo] = {}


def get_connection_id(websocket: WebSocket) -> int:
    return id(websocket)


async def connect(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    conn_id = get_connection_id(websocket)
    connection_metadata[conn_id] = ConnectionInfo()
    logger.debug(f"WebSocket connected: {conn_id}")


async def connect_to_donation(
    websocket: WebSocket, donation_id: str, user_id: Optional[str] = None
):
    """Connect a WebSocket to a specific donation room for targeted broadcasts."""
    await websocket.accept()

    conn_id = get_connection_id(websocket)
    if conn_id not in connection_metadata:
        connection_metadata[conn_id] = ConnectionInfo()

    connection_metadata[conn_id].donation_id = donation_id
    connection_metadata[conn_id].user_id = user_id
    connection_metadata[conn_id].connected_at = datetime.now(timezone.utc)

    if donation_id not in donation_rooms:
        donation_rooms[donation_id] = []

    donation_rooms[donation_id].append(websocket)
    logger.info(f"WebSocket connected to donation room: {donation_id}, user: {user_id}")


async def disconnect(websocket: WebSocket):
    conn_id = get_connection_id(websocket)

    if conn_id in connection_metadata:
        metadata = connection_metadata[conn_id]
        logger.debug(
            f"WebSocket disconnect: user={metadata.user_id}, donation={metadata.donation_id}, messages={metadata.message_count}, duration={(datetime.now(timezone.utc) - metadata.connected_at).total_seconds()}s"
        )
        del connection_metadata[conn_id]

    if websocket in active_connections:
        active_connections.remove(websocket)

    for donation_id, connections in list(donation_rooms.items()):
        if websocket in connections:
            connections.remove(websocket)
            if not connections:
                del donation_rooms[donation_id]
            logger.info(f"WebSocket disconnected from donation room: {donation_id}")


async def broadcast(message: dict):
    stale_connections = []
    for connection in active_connections:
        try:
            await connection.send_json(message)
            conn_id = get_connection_id(connection)
            if conn_id in connection_metadata:
                connection_metadata[conn_id].message_count += 1
                connection_metadata[conn_id].last_heartbeat = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"WebSocket broadcast error: {e}")
            stale_connections.append(connection)

    for stale in stale_connections:
        if stale in active_connections:
            active_connections.remove(stale)


async def broadcast_to_donation(donation_id: str, message: dict):
    """Broadcast a message to all WebSockets subscribed to a specific donation."""
    if donation_id not in donation_rooms:
        logger.debug(f"No active connections for donation: {donation_id}")
        return

    stale_connections = []
    for connection in donation_rooms[donation_id]:
        try:
            await connection.send_json(message)
            conn_id = get_connection_id(connection)
            if conn_id in connection_metadata:
                connection_metadata[conn_id].message_count += 1
                connection_metadata[conn_id].last_heartbeat = datetime.now(timezone.utc)
            logger.debug(
                f"Broadcast to donation {donation_id}: {message.get('type', 'unknown')}"
            )
        except Exception as e:
            logger.error(f"WebSocket broadcast to donation {donation_id} error: {e}")
            stale_connections.append(connection)

    for stale in stale_connections:
        if stale in donation_rooms.get(donation_id, []):
            donation_rooms[donation_id].remove(stale)

    if donation_id in donation_rooms and not donation_rooms[donation_id]:
        del donation_rooms[donation_id]


def get_connection_stats() -> dict:
    """Get current WebSocket connection statistics."""
    total_connections = len(active_connections)
    total_donations = len(donation_rooms)

    return {
        "total_connections": total_connections,
        "total_donation_rooms": total_donations,
        "donations": {
            donation_id: len(connections)
            for donation_id, connections in donation_rooms.items()
        },
        "active_connections_detail": [
            {
                "donation_id": meta.donation_id,
                "user_id": meta.user_id,
                "connected_at": meta.connected_at.isoformat(),
                "last_heartbeat": meta.last_heartbeat.isoformat()
                if meta.last_heartbeat
                else None,
                "message_count": meta.message_count,
            }
            for meta in connection_metadata.values()
            if meta.donation_id
        ],
    }


async def handle_location_websocket(websocket: WebSocket, donation_id: str, token: str):
    """
    Handle authenticated WebSocket connection for real-time location tracking.

    Validates:
    - JWT token
    - User has access to this donation (donor, NGO, or assigned volunteer)
    """
    from jose import jwt
    from jose.exceptions import JWTError
    from pydantic import ValidationError

    from app.core.config import settings
    from app.core import security
    from app.domain import models
    from app.infrastructure.database import SessionLocal

    user = None
    db = None

    try:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
            )
            token_sub = payload.get("sub")
        except (JWTError, ValidationError):
            await websocket.close(code=4001, reason="Invalid token")
            return

        if not token_sub:
            await websocket.close(code=4001, reason="Invalid token")
            return

        db = SessionLocal()

        import uuid

        try:
            user_uuid = uuid.UUID(str(token_sub))
        except (ValueError, AttributeError):
            await websocket.close(code=4001, reason="Invalid token sub")
            return

        user = db.query(models.User).filter(models.User.id == user_uuid).first()
        if not user:
            await websocket.close(code=4001, reason="User not found")
            return

        import uuid

        try:
            donation_uuid = uuid.UUID(donation_id)
        except ValueError:
            await websocket.close(code=4002, reason="Invalid donation ID")
            return

        donation = (
            db.query(models.Donation)
            .filter(models.Donation.id == donation_uuid)
            .first()
        )
        if not donation:
            await websocket.close(code=4004, reason="Donation not found")
            return

        has_access = False
        if user.role == models.RoleEnum.DONOR and donation.donor_id == user.id:
            has_access = True
        elif user.role == models.RoleEnum.NGO and donation.ngo_id == user.id:
            has_access = True
        elif (
            user.role == models.RoleEnum.VOLUNTEER and donation.volunteer_id == user.id
        ):
            has_access = True

        if not has_access:
            await websocket.close(code=4003, reason="Access denied")
            return

        await connect_to_donation(websocket, donation_id)
        logger.info(f"User {user.email} connected to donation tracking: {donation_id}")

        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_json(
                            {
                                "type": "pong",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            await disconnect(websocket)
            logger.info(
                f"User {user.email} disconnected from donation tracking: {donation_id}"
            )
    except Exception as e:
        logger.error(f"Location WebSocket error: {e}")
        try:
            await websocket.close(code=4000, reason="Server error")
        except:
            pass
    finally:
        if db:
            db.close()

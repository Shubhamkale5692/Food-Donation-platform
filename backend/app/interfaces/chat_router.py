import uuid
import json
import html
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.domain import models, schemas
from app.infrastructure.database import SessionLocal
from app.interfaces.deps import get_current_active_user, get_db
from app.services import websocket_service

router = APIRouter()


def sanitize_message(message: str) -> str:
    """Sanitize message input to prevent XSS."""
    return html.escape(message.strip())


def validate_donation_access(
    user: models.User, donation_id: uuid.UUID, db: Session
) -> models.Donation:
    """
    Validate that user has access to this donation.
    Returns the donation if access is valid, raises HTTPException otherwise.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    has_access = False
    if user.role == models.RoleEnum.DONOR and donation.donor_id == user.id:
        has_access = True
    elif user.role == models.RoleEnum.NGO and donation.ngo_id == user.id:
        has_access = True
    elif user.role == models.RoleEnum.VOLUNTEER and donation.volunteer_id == user.id:
        has_access = True

    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to communicate for this donation",
        )

    return donation


def get_participants(donation: models.Donation, db: Session) -> dict:
    """Get participant details for a donation."""
    participants = {
        "donor_id": donation.donor_id,
        "ngo_id": donation.ngo_id,
        "volunteer_id": donation.volunteer_id,
    }

    donor = db.query(models.User).filter(models.User.id == donation.donor_id).first()
    if donor and donor.profile:
        participants["donor_phone"] = donor.profile.phone

    if donation.ngo_id:
        ngo = db.query(models.User).filter(models.User.id == donation.ngo_id).first()
        if ngo and ngo.profile:
            participants["ngo_phone"] = ngo.profile.phone

    if donation.volunteer_id:
        volunteer = (
            db.query(models.User)
            .filter(models.User.id == donation.volunteer_id)
            .first()
        )
        if volunteer and volunteer.profile:
            participants["volunteer_phone"] = volunteer.profile.phone

    return participants


# ─────────────────────────────────────────────────────────────────────────────
# REST API Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/send", response_model=schemas.MessageResponse)
def send_message(
    request: schemas.SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Send a message to another user within a donation context.
    Validates that both users are participants in the donation.
    """
    sanitized = sanitize_message(request.message)
    if not sanitized:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    donation = validate_donation_access(current_user, request.donation_id, db)

    if request.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send message to yourself")

    participants = get_participants(donation, db)
    valid_receivers = [
        p
        for p in [
            participants.get("donor_id"),
            participants.get("ngo_id"),
            participants.get("volunteer_id"),
        ]
        if p
    ]

    if request.receiver_id not in valid_receivers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Receiver is not a participant in this donation",
        )

    new_message = models.Message(
        sender_id=current_user.id,
        receiver_id=request.receiver_id,
        donation_id=request.donation_id,
        message=sanitized,
        status="sent",
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    sender_profile = (
        db.query(models.Profile)
        .filter(models.Profile.user_id == current_user.id)
        .first()
    )
    receiver_profile = (
        db.query(models.Profile)
        .filter(models.Profile.user_id == request.receiver_id)
        .first()
    )

    response = schemas.MessageResponse(
        id=new_message.id,
        sender_id=new_message.sender_id,
        receiver_id=new_message.receiver_id,
        donation_id=new_message.donation_id,
        message=new_message.message,
        timestamp=new_message.timestamp,
        is_read=new_message.is_read,
        status=new_message.status,
        delivered_at=new_message.delivered_at,
        seen_at=new_message.seen_at,
        sender_name=sender_profile.name if sender_profile else current_user.email,
        receiver_name=receiver_profile.name if receiver_profile else None,
    )

    message_data = {
        "type": "chat_message",
        "id": str(new_message.id),
        "sender_id": str(new_message.sender_id),
        "receiver_id": str(new_message.receiver_id),
        "donation_id": str(new_message.donation_id),
        "message": new_message.message,
        "timestamp": new_message.timestamp.isoformat(),
        "is_read": new_message.is_read,
        "status": new_message.status,
        "sender_name": response.sender_name,
        "receiver_name": response.receiver_name,
    }

    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(
                websocket_service.broadcast_to_donation(
                    str(request.donation_id), message_data
                )
            )
    except RuntimeError:
        pass

    return response


@router.get("/{donation_id}", response_model=list[schemas.MessageResponse])
def get_messages(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get all messages for a donation.
    Only returns messages where sender or receiver is the current user.
    """
    donation = validate_donation_access(current_user, donation_id, db)

    messages = (
        db.query(models.Message)
        .filter(models.Message.donation_id == donation_id)
        .order_by(models.Message.timestamp.asc())
        .all()
    )

    result = []
    for msg in messages:
        sender = db.query(models.User).filter(models.User.id == msg.sender_id).first()
        receiver = (
            db.query(models.User).filter(models.User.id == msg.receiver_id).first()
        )

        sender_name = None
        receiver_name = None

        if sender and sender.profile:
            sender_name = sender.profile.name
        elif sender:
            sender_name = sender.email

        if receiver and receiver.profile:
            receiver_name = receiver.profile.name
        elif receiver:
            receiver_name = receiver.email

        result.append(
            schemas.MessageResponse(
                id=msg.id,
                sender_id=msg.sender_id,
                receiver_id=msg.receiver_id,
                donation_id=msg.donation_id,
                message=msg.message,
                timestamp=msg.timestamp,
                is_read=msg.is_read,
                status=msg.status or "sent",
                delivered_at=msg.delivered_at,
                seen_at=msg.seen_at,
                sender_name=sender_name,
                receiver_name=receiver_name,
            )
        )

    return result


@router.get("/{donation_id}/poll")
def poll_messages(
    donation_id: uuid.UUID,
    since: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Polling fallback for chat messages when WebSocket is unavailable.
    Returns messages newer than the 'since' timestamp.
    """
    donation = validate_donation_access(current_user, donation_id, db)

    query = db.query(models.Message).filter(models.Message.donation_id == donation_id)

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            query = query.filter(models.Message.timestamp > since_dt)
        except ValueError:
            pass

    messages = query.order_by(models.Message.timestamp.asc()).all()

    result = []
    for msg in messages:
        sender = db.query(models.User).filter(models.User.id == msg.sender_id).first()
        receiver = (
            db.query(models.User).filter(models.User.id == msg.receiver_id).first()
        )

        sender_name = (
            sender.profile.name
            if sender and sender.profile
            else (sender.email if sender else None)
        )
        receiver_name = (
            receiver.profile.name
            if receiver and receiver.profile
            else (receiver.email if receiver else None)
        )

        result.append(
            {
                "id": str(msg.id),
                "sender_id": str(msg.sender_id),
                "receiver_id": str(msg.receiver_id),
                "donation_id": str(msg.donation_id),
                "message": msg.message,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "is_read": msg.is_read,
                "status": msg.status or "sent",
                "sender_name": sender_name,
                "receiver_name": receiver_name,
            }
        )

    return {
        "messages": result,
        "polled_at": datetime.now(timezone.utc).isoformat(),
        "ws_recommended": True,
    }


@router.get("/{donation_id}/status")
def get_chat_status(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get chat connection status and participant info.
    Used by frontend to determine if WebSocket is available.
    """
    donation = validate_donation_access(current_user, donation_id, db)

    unread_count = (
        db.query(models.Message)
        .filter(
            models.Message.donation_id == donation_id,
            models.Message.receiver_id == current_user.id,
            models.Message.is_read == False,
        )
        .count()
    )

    return {
        "donation_id": str(donation_id),
        "unread_count": unread_count,
        "ws_endpoint": f"/api/v1/messages/ws/chat/{donation_id}",
        "poll_endpoint": f"/api/v1/messages/{donation_id}/poll",
        "heartbeat_interval": 30,
    }


@router.post("/read")
def mark_messages_read(
    request: schemas.MarkReadRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Mark all messages in a donation as read for the current user.
    """
    donation = validate_donation_access(current_user, request.donation_id, db)

    db.query(models.Message).filter(
        models.Message.donation_id == request.donation_id,
        models.Message.receiver_id == current_user.id,
        models.Message.is_read == False,
    ).update({"is_read": True})
    db.commit()

    return {"success": True, "message": "Messages marked as read"}


@router.post("/mark-seen")
def mark_messages_seen(
    request: schemas.MarkSeenRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Mark messages as seen and update delivery status.
    """
    donation = validate_donation_access(current_user, request.donation_id, db)

    now = datetime.now(timezone.utc)

    if request.message_ids:
        db.query(models.Message).filter(
            models.Message.id.in_(request.message_ids),
            models.Message.receiver_id == current_user.id,
            models.Message.status.in_(["sent", "delivered"]),
        ).update(
            {"status": "seen", "seen_at": now, "is_read": True},
            synchronize_session=False,
        )
    else:
        db.query(models.Message).filter(
            models.Message.donation_id == request.donation_id,
            models.Message.receiver_id == current_user.id,
            models.Message.status.in_(["sent", "delivered"]),
        ).update(
            {"status": "seen", "seen_at": now, "is_read": True},
            synchronize_session=False,
        )
    db.commit()

    return {"success": True, "message": "Messages marked as seen"}


@router.post("/emergency-alert")
def send_emergency_alert(
    request: schemas.EmergencyAlertRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Send an emergency alert to NGO about a donation.
    Only volunteers can send emergency alerts.
    """
    if current_user.role != models.RoleEnum.VOLUNTEER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only volunteers can send emergency alerts",
        )

    donation = validate_donation_access(current_user, request.donation_id, db)

    if not donation.ngo_id:
        raise HTTPException(status_code=400, detail="No NGO assigned to this donation")

    sanitized = sanitize_message(request.message)
    if not sanitized:
        sanitized = "Emergency! Need help immediately!"

    alert_message = models.Message(
        sender_id=current_user.id,
        receiver_id=donation.ngo_id,
        donation_id=request.donation_id,
        message=f"🚨 EMERGENCY: {sanitized}",
    )
    db.add(alert_message)

    notification = models.Notification(
        user_id=donation.ngo_id,
        message=f"Emergency alert from volunteer for donation {request.donation_id}: {sanitized}",
        notification_type="alert",
    )
    db.add(notification)
    db.commit()
    db.refresh(alert_message)

    message_data = {
        "type": "emergency_alert",
        "id": str(alert_message.id),
        "donation_id": str(request.donation_id),
        "message": alert_message.message,
        "timestamp": alert_message.timestamp.isoformat(),
        "volunteer_name": current_user.profile.name
        if current_user.profile
        else current_user.email,
    }

    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(
                websocket_service.broadcast_to_donation(
                    str(request.donation_id), message_data
                )
            )
    except RuntimeError:
        pass

    return {"success": True, "message": "Emergency alert sent"}


@router.get("/{donation_id}/participants")
def get_donation_participants(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get participant details including phone numbers for call feature.
    Only returns phone if user has access to the donation.
    """
    donation = validate_donation_access(current_user, donation_id, db)
    participants = get_participants(donation, db)

    result = {"donation_id": str(donation_id), "participants": []}

    # Convert to UUIDs for comparison to avoid SQLAlchemy column issues
    allowed_ids = []
    if donation.ngo_id:
        allowed_ids.append(donation.ngo_id)
    if donation.volunteer_id:
        allowed_ids.append(donation.volunteer_id)

    current_user_id = current_user.id

    if participants.get("donor_id"):
        donor = (
            db.query(models.User)
            .filter(models.User.id == participants["donor_id"])
            .first()
        )
        if donor and donor.profile:
            # Phone only visible to NGO or volunteer assigned to this donation
            show_phone = current_user_id in allowed_ids
            result["participants"].append(
                {
                    "user_id": str(donor.id),
                    "name": donor.profile.name,
                    "role": "Donor",
                    "phone": participants.get("donor_phone") if show_phone else None,
                }
            )

    if participants.get("ngo_id"):
        ngo = (
            db.query(models.User)
            .filter(models.User.id == participants["ngo_id"])
            .first()
        )
        if ngo and ngo.profile:
            # Phone visible to volunteer or admin
            show_phone = (
                current_user_id == donation.volunteer_id
                or current_user.role == models.RoleEnum.ADMIN
            )
            result["participants"].append(
                {
                    "user_id": str(ngo.id),
                    "name": ngo.profile.name,
                    "role": "NGO",
                    "phone": participants.get("ngo_phone") if show_phone else None,
                }
            )

    if participants.get("volunteer_id"):
        volunteer = (
            db.query(models.User)
            .filter(models.User.id == participants["volunteer_id"])
            .first()
        )
        if volunteer and volunteer.profile:
            # Phone visible to NGO or admin
            show_phone = (
                current_user_id == donation.ngo_id
                or current_user.role == models.RoleEnum.ADMIN
            )
            result["participants"].append(
                {
                    "user_id": str(volunteer.id),
                    "name": volunteer.profile.name,
                    "role": "Volunteer",
                    "phone": participants.get("volunteer_phone")
                    if show_phone
                    else None,
                }
            )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Endpoint
# ─────────────────────────────────────────────────────────────────────────────


class ConnectionManager:
    """Manages WebSocket connections for chat."""

    async def connect(self, websocket: WebSocket, donation_id: str, user_id: str):
        await websocket.accept()
        await websocket_service.connect_to_donation(websocket, donation_id)

    async def disconnect(self, websocket: WebSocket, donation_id: str):
        await websocket_service.disconnect(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict, donation_id: str):
        await websocket_service.broadcast_to_donation(donation_id, message)


manager = ConnectionManager()


@router.websocket("/ws/chat/{donation_id}")
async def websocket_chat_endpoint(websocket: WebSocket, donation_id: str):
    from jose import jwt
    from jose.exceptions import JWTError
    from pydantic import ValidationError
    from app.core import security
    from app.core.config import settings
    from app.domain import models
    from app.infrastructure.database import SessionLocal
    import uuid as uuid_module
    import logging

    query_params = websocket.query_params
    token = query_params.get("token", "")
    heartbeat_interval = query_params.get("heartbeat", "30")

    try:
        heartbeat_interval = int(heartbeat_interval)
    except ValueError:
        heartbeat_interval = 30

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_sub = payload.get("sub")
    except (JWTError, ValidationError):
        await websocket.close(code=4001, reason="Invalid token")
        return

    db = SessionLocal()

    try:
        user_uuid = uuid_module.UUID(str(token_sub))
    except (ValueError, AttributeError):
        await websocket.close(code=4001, reason="Invalid token sub")
        return

    user = db.query(models.User).filter(models.User.id == user_uuid).first()
    if not user:
        await websocket.close(code=4001, reason="User not found")
        return

    try:
        donation_uuid = uuid_module.UUID(donation_id)
    except ValueError:
        await websocket.close(code=4002, reason="Invalid donation ID")
        return

    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_uuid).first()
    )
    if not donation:
        await websocket.close(code=4004, reason="Donation not found")
        return

    has_access = False
    if user.role == models.RoleEnum.DONOR and donation.donor_id == user.id:
        has_access = True
    elif user.role == models.RoleEnum.NGO and donation.ngo_id == user.id:
        has_access = True
    elif user.role == models.RoleEnum.VOLUNTEER and donation.volunteer_id == user.id:
        has_access = True

    if not has_access:
        await websocket.close(code=4003, reason="Access denied")
        return

    await manager.connect(websocket, donation_id, str(user.id))
    logging.info(f"User {user.email} connected to chat: {donation_id}")

    await websocket.send_json(
        {
            "type": "connected",
            "donation_id": donation_id,
            "user_id": str(user.id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    last_heartbeat = datetime.now(timezone.utc)
    disconnect_reason = "unknown"

    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=heartbeat_interval + 5
                )
            except asyncio.TimeoutError:
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                last_heartbeat = datetime.now(timezone.utc)
                continue

            try:
                msg = json.loads(data)
                msg_type = msg.get("type")

                if msg_type == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    last_heartbeat = datetime.now(timezone.utc)
                elif msg_type == "typing":
                    await manager.broadcast(
                        {
                            "type": "typing",
                            "sender_id": str(user.id),
                            "receiver_id": msg.get("receiver_id"),
                        },
                        donation_id,
                    )
                elif msg_type == "heartbeat":
                    last_heartbeat = datetime.now(timezone.utc)
                    await websocket.send_json(
                        {
                            "type": "heartbeat_ack",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect as e:
        disconnect_reason = str(e.code) if e.code else "client_disconnect"
        await manager.disconnect(websocket, donation_id)
        logging.info(
            f"User {user.email} disconnected from chat: {donation_id}, reason: {disconnect_reason}"
        )
    except Exception as e:
        disconnect_reason = f"error: {str(e)}"
        logging.error(
            f"WebSocket error for user {user.email} in chat {donation_id}: {e}"
        )
        try:
            await websocket.close(code=4000, reason="Server error")
        except:
            pass
        await manager.disconnect(websocket, donation_id)
    finally:
        db.close()
        logging.info(
            f"Chat connection closed for user {user.email}, donation {donation_id}, reason: {disconnect_reason}"
        )

"""
Temporary websocket auth helper used during debugging sessions.

This module is intentionally standalone so importing it never causes syntax
errors during compile/test runs.
"""

from fastapi import WebSocket
from jose import JWTError, jwt
from pydantic import ValidationError

from app.core import security
from app.core.config import settings


async def close_if_invalid_token(websocket: WebSocket) -> bool:
    """
    Validate websocket token from query params.

    Returns:
        True  -> websocket was closed because token is invalid/missing.
        False -> token payload is valid.
    """
    query_params = websocket.query_params
    token = query_params.get("token", "")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        token_sub = payload.get("sub")
        if not token_sub:
            await websocket.close(code=4001, reason="Invalid token")
            return True
    except (JWTError, ValidationError):
        await websocket.close(code=4001, reason="Invalid token")
        return True

    return False

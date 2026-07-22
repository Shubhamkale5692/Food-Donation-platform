from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt
import bcrypt
from app.core.config import settings

ALGORITHM = "HS256"
MIN_PASSWORD_LENGTH = 8


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password meets minimum strength requirements.
    Returns (is_valid, error_message).
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
    return True, ""


def _normalize_password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:72]


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # Handle bcrypt hashes (current format)
        password_bytes = _normalize_password_bytes(plain_password)
        hash_bytes = hashed_password.encode("utf-8")
        if bcrypt.checkpw(password_bytes, hash_bytes):
            return True

        # Handle legacy MD5 hashes (for compatibility with old data)
        import hashlib

        md5_hash = hashlib.md5(password_bytes).hexdigest()
        if md5_hash == hashed_password:
            return True

    except Exception as e:
        # Log the error for debugging
        import logging

        logging.getLogger("foodbridge.auth").warning(
            f"Password verification error: {e}"
        )
        pass
    return False


def get_password_hash(password: str) -> str:
    password_bytes = _normalize_password_bytes(password)
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")

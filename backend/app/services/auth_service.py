from sqlalchemy.orm import Session
from app.domain import models, schemas
from app.core import security
from fastapi import HTTPException, status
from typing import Optional


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # NGOs need admin approval
    is_verified = True
    if user.role == models.RoleEnum.NGO:
        is_verified = False

    hashed_password = security.get_password_hash(user.password)

    db_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=hashed_password,
        role=user.role,
        is_active=True,
        is_verified=is_verified,
        ngo_id=user.ngo_id if user.role == models.RoleEnum.VOLUNTEER else None,
        volunteer_status="pending" if user.role == models.RoleEnum.VOLUNTEER else None,
        status="pending" if user.role == models.RoleEnum.VOLUNTEER else None,
        availability="available" if user.role == models.RoleEnum.VOLUNTEER else None,
    )
    db.add(db_user)
    db.flush()  # Flush to get the user ID before creating profile

    # Create profile in same transaction
    db_profile = models.Profile(user_id=db_user.id, name=user.name)
    db.add(db_profile)

    db.commit()
    db.refresh(db_user)

    return db_user


def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not security.verify_password(password, user.password_hash):
        return None
    return user

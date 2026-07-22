from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core import security
from app.domain import schemas, models
from app.services import auth_service
from app.infrastructure.database import get_db
from app.interfaces.deps import get_current_user

router = APIRouter()


@router.post("/register", response_model=schemas.UserResponse)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.
    """
    user = auth_service.get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    user = auth_service.create_user(db, user=user_in)
    return user


@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.LoginRequest, db: Session = Depends(get_db)):
    """
    Standard JSON token login, get an access token for future requests
    """
    import logging

    log = logging.getLogger("foodbridge.auth.login")
    log.info("Login request received for email=%s", credentials.email)

    # First check if user exists
    user = auth_service.get_user_by_email(db, email=credentials.email)
    if not user:
        log.warning(
            "Login failed for email=%s: user not found in database", credentials.email
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Log found user details
    log.info(
        "User found in DB: id=%s, role=%s, is_active=%s, is_verified=%s, volunteer_status=%s",
        user.id,
        user.role,
        user.is_active,
        user.is_verified,
        user.volunteer_status,
    )

    # Check password verification
    password_valid = security.verify_password(credentials.password, user.password_hash)
    log.info("Password verification result: %s", password_valid)

    if not password_valid:
        log.warning("Login failed for email=%s: password mismatch", credentials.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        if user.role == models.RoleEnum.NGO:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="NGO account has been rejected by admin",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    if user.role == models.RoleEnum.NGO and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="NGO not approved yet - awaiting admin verification",
        )

    if user.role == models.RoleEnum.VOLUNTEER:
        v_status = (user.volunteer_status or "pending").lower()
        if v_status == "pending":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your volunteer account is waiting for NGO approval",
            )
        elif v_status == "rejected":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your volunteer request was rejected by NGO",
            )
        elif v_status != "approved":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account not approved",
            )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(user.id, expires_delta=access_token_expires)
    log.info("Login succeeded for email=%s role=%s", credentials.email, user.role.value)

    return schemas.Token(
        access_token=token,
        token_type="bearer",
        role=user.role.value,
        success=True,
        user=schemas.TokenUser(
            id=user.id,
            name=user.profile.name if user.profile else user.email.split("@")[0],
            email=user.email,
        ),
    )


@router.get("/ngos")
def get_verified_ngos(db: Session = Depends(get_db)):
    """
    Get list of verified NGOs for volunteer registration.
    Returns id, email, and profile name for dropdown display.
    """
    ngos = (
        db.query(models.User)
        .filter(
            models.User.role == models.RoleEnum.NGO, models.User.is_verified == True
        )
        .all()
    )
    result = []
    for ngo in ngos:
        result.append(
            {
                "id": str(ngo.id),
                "email": ngo.email,
                "name": ngo.profile.name if ngo.profile else ngo.email.split("@")[0],
            }
        )
    return result


@router.post("/logout")
def logout(current_user: models.User = Depends(get_current_user)):
    """
    Logout user.
    """
    return {"message": "Successfully logged out"}


# ─────────────────────────────────────────────────────────────────────────────
#  GET /auth/profile  – Current user profile
#  PUT /auth/profile  – Update current user profile
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/profile")
def get_user_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Get current user's profile information.
    """
    profile = (
        db.query(models.Profile)
        .filter(models.Profile.user_id == current_user.id)
        .first()
    )
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": profile.name
        if profile
        else current_user.name or current_user.email.split("@")[0],
        "phone": profile.phone if profile else "",
        "address": profile.address if profile else "",
        "latitude": profile.latitude if profile else None,
        "longitude": profile.longitude if profile else None,
        "role": current_user.role.value if current_user.role else "",
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at.strftime("%b %d, %Y")
        if current_user.created_at
        else "",
    }


@router.put("/profile")
def update_user_profile(
    body: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Update current user's profile information.
    """
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid request body")

    profile = (
        db.query(models.Profile)
        .filter(models.Profile.user_id == current_user.id)
        .first()
    )
    if not profile:
        fallback_name = current_user.name or current_user.email.split("@")[0]
        profile = models.Profile(user_id=current_user.id, name=fallback_name)
        db.add(profile)
        db.flush()

    if "name" in body:
        profile.name = body["name"]
    if "phone" in body:
        profile.phone = body["phone"]
    if "address" in body:
        profile.address = body["address"]
    if "latitude" in body and body["latitude"] is not None:
        profile.latitude = body["latitude"]
    if "longitude" in body and body["longitude"] is not None:
        profile.longitude = body["longitude"]

    db.commit()
    db.refresh(profile)

    return {
        "message": "Profile updated successfully",
        "profile": {
            "name": profile.name,
            "phone": profile.phone,
            "address": profile.address,
            "latitude": profile.latitude,
            "longitude": profile.longitude,
        },
    }

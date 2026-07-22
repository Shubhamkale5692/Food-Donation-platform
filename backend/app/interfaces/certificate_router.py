import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.domain import models, schemas
from app.services import certificate_service
from app.interfaces.deps import get_db, get_current_active_user, RoleChecker

logger = logging.getLogger(__name__)

router = APIRouter()


class CertificateResponse(schemas.BaseModel):
    id: UUID
    user_id: UUID
    role: str
    level: str
    total_count: int
    certificate_id: str
    issued_at: str
    certificate_url: str
    email_sent: bool

    model_config = {"from_attributes": True}


class AchievementResponse(schemas.BaseModel):
    role: str
    current_level: str | None
    next_level: str | None
    total_completed: int
    remaining: int


@router.get("/certificates", response_model=List[CertificateResponse])
def get_user_certificates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get all certificates for the current user.
    """
    certs = certificate_service.get_user_certificates(db, current_user.id)
    return [
        CertificateResponse(
            id=c.id,
            user_id=c.user_id,
            role=c.role,
            level=c.level,
            total_count=c.total_count,
            certificate_id=c.certificate_id,
            issued_at=c.issued_at.isoformat() if c.issued_at else "",
            certificate_url=c.certificate_url or "",
            email_sent=c.email_sent,
        )
        for c in certs
    ]


@router.get("/achievements", response_model=List[AchievementResponse])
def get_user_achievements(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get achievements for the current user (both donor and volunteer roles).
    """
    achievements = []

    if current_user.role in [models.RoleEnum.DONOR, models.RoleEnum.ADMIN]:
        donor_achievement = certificate_service.get_user_achievement(
            db, current_user.id, "donor"
        )
        if donor_achievement:
            achievements.append(AchievementResponse(**donor_achievement))

    if current_user.role in [models.RoleEnum.VOLUNTEER, models.RoleEnum.ADMIN]:
        vol_achievement = certificate_service.get_user_achievement(
            db, current_user.id, "volunteer"
        )
        if vol_achievement:
            achievements.append(AchievementResponse(**vol_achievement))

    if current_user.role in [models.RoleEnum.NGO]:
        donor_achievement = certificate_service.get_user_achievement(
            db, current_user.id, "donor"
        )
        if donor_achievement:
            achievements.append(AchievementResponse(**donor_achievement))

    return achievements


@router.post("/check-certificate")
def check_and_generate_certificate(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Manually trigger certificate check and generation.
    This can be called after status updates to generate certificates.
    """
    role = None
    if current_user.role == models.RoleEnum.DONOR:
        role = "donor"
    elif current_user.role == models.RoleEnum.VOLUNTEER:
        role = "volunteer"

    if not role:
        raise HTTPException(
            status_code=400, detail="User role not eligible for certificates"
        )

    cert = certificate_service.check_and_generate_certificate(
        current_user.id, role, db, background_tasks
    )

    if cert:
        return {
            "success": True,
            "message": f"Certificate generated: {cert.level}",
            "certificate_id": cert.certificate_id,
        }
    else:
        return {
            "success": False,
            "message": "No certificate available for current status",
        }

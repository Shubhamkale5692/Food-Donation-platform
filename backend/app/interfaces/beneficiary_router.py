"""
Beneficiary API Router
Provides CRUD operations for beneficiaries/recipients.
"""

from typing import List, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.domain import schemas, models
from app.interfaces.deps import get_db, get_current_active_user, RoleChecker

router = APIRouter(prefix="/beneficiaries", tags=["Beneficiaries"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=schemas.BeneficiaryResponse)
def create_beneficiary(
    beneficiary_in: schemas.BeneficiaryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        RoleChecker([models.RoleEnum.NGO, models.RoleEnum.ADMIN])
    ),
):
    """
    Create a new beneficiary/recipient.
    Only NGO or Admin can create beneficiaries.
    """
    beneficiary = models.Beneficiary(
        name=beneficiary_in.name,
        type=beneficiary_in.type,
        address=beneficiary_in.address,
        latitude=beneficiary_in.latitude,
        longitude=beneficiary_in.longitude,
        contact_number=beneficiary_in.contact_number,
        capacity=beneficiary_in.capacity,
    )
    db.add(beneficiary)
    db.commit()
    db.refresh(beneficiary)
    logger.info("Beneficiary created: %s by user %s", beneficiary.id, current_user.id)
    return beneficiary


@router.get("/", response_model=List[schemas.BeneficiaryResponse])
def read_beneficiaries(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    type_filter: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get list of beneficiaries.
    Optional filtering by type and active status.
    """
    query = db.query(models.Beneficiary)

    # Return ALL beneficiaries (no filter by default)
    logger.info(f"read_beneficiaries called by user {current_user.id}")

    beneficiaries = query.limit(limit).all()
    logger.info(f"Found {len(beneficiaries)} beneficiaries")
    return beneficiaries


@router.get("/{beneficiary_id}", response_model=schemas.BeneficiaryResponse)
def read_beneficiary(
    beneficiary_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get a specific beneficiary by ID.
    """
    from sqlalchemy.orm.exc import NoResultFound
    import uuid

    try:
        bid = uuid.UUID(beneficiary_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid beneficiary ID format")

    beneficiary = (
        db.query(models.Beneficiary).filter(models.Beneficiary.id == bid).first()
    )
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    return beneficiary


@router.put("/{beneficiary_id}", response_model=schemas.BeneficiaryResponse)
def update_beneficiary(
    beneficiary_id: str,
    beneficiary_update: schemas.BeneficiaryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        RoleChecker([models.RoleEnum.NGO, models.RoleEnum.ADMIN])
    ),
):
    """
    Update a beneficiary's information.
    Only NGO or Admin can update beneficiaries.
    """
    import uuid

    try:
        bid = uuid.UUID(beneficiary_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid beneficiary ID format")

    beneficiary = (
        db.query(models.Beneficiary).filter(models.Beneficiary.id == bid).first()
    )
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    # Update fields if provided
    update_data = beneficiary_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(beneficiary, field, value)

    db.commit()
    db.refresh(beneficiary)
    logger.info("Beneficiary updated: %s by user %s", beneficiary.id, current_user.id)
    return beneficiary


@router.delete("/{beneficiary_id}")
def delete_beneficiary(
    beneficiary_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        RoleChecker([models.RoleEnum.NGO, models.RoleEnum.ADMIN])
    ),
):
    """
    Soft delete a beneficiary (mark as inactive).
    Only NGO or Admin can delete beneficiaries.
    """
    import uuid

    try:
        bid = uuid.UUID(beneficiary_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid beneficiary ID format")

    beneficiary = (
        db.query(models.Beneficiary).filter(models.Beneficiary.id == bid).first()
    )
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    # Hard delete - permanently remove from DB
    db.delete(beneficiary)
    db.commit()

    logger.info(
        "Beneficiary permanently deleted: %s by user %s", beneficiary_id, current_user.id
    )
    return {
        "message": "Beneficiary deleted permanently",
        "beneficiary_id": str(beneficiary_id),
    }


@router.post("/assign-to-donation")
def assign_beneficiary_to_donation(
    *,
    donation_id: str,
    beneficiary_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        RoleChecker([models.RoleEnum.NGO, models.RoleEnum.ADMIN])
    ),
):
    """
    Assign a beneficiary to a donation for delivery.
    Used during distribution management phase.
    """
    import uuid

    try:
        did = uuid.UUID(donation_id)
        bid = uuid.UUID(beneficiary_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    # Check donation exists
    donation = db.query(models.Donation).filter(models.Donation.id == did).first()
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    # Check beneficiary exists
    beneficiary = (
        db.query(models.Beneficiary).filter(models.Beneficiary.id == bid).first()
    )
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    if not beneficiary.is_active:
        raise HTTPException(
            status_code=400, detail="Cannot assign inactive beneficiary"
        )

    # Assign beneficiary to donation
    donation.beneficiary_id = bid
    db.commit()
    db.refresh(donation)

    logger.info(
        "Beneficiary %s assigned to donation %s by user %s",
        beneficiary_id,
        donation_id,
        current_user.id,
    )

    return {
        "success": True,
        "message": f"Beneficiary '{beneficiary.name}' assigned to donation",
        "donation_id": str(donation_id),
        "beneficiary_id": str(beneficiary_id),
        "beneficiary_name": beneficiary.name,
    }


@router.get("/nearby/list")
def get_nearby_beneficiaries(
    latitude: float,
    longitude: float,
    radius_km: float = 10.0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get beneficiaries near a given location.
    Uses simple lat/lng bounding box for efficiency.
    """
    from sqlalchemy import and_

    # Simple bounding box calculation (approximate)
    lat_delta = radius_km / 111.0  # 1 degree latitude ≈ 111 km
    lng_delta = radius_km / (111.0 * 0.7)  # Approximate longitude at mid-latitudes

    beneficiaries = (
        db.query(models.Beneficiary)
        .filter(
            and_(
                models.Beneficiary.is_active == True,
                models.Beneficiary.latitude.between(
                    latitude - lat_delta, latitude + lat_delta
                ),
                models.Beneficiary.longitude.between(
                    longitude - lng_delta, longitude + lng_delta
                ),
            )
        )
        .limit(50)
        .all()
    )

    return {
        "beneficiaries": [
            {
                "id": str(b.id),
                "name": b.name,
                "type": b.type.value,
                "address": b.address,
                "latitude": b.latitude,
                "longitude": b.longitude,
                "contact_number": b.contact_number,
                "capacity": b.capacity,
            }
            for b in beneficiaries
        ],
        "count": len(beneficiaries),
    }

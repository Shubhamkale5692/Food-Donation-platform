from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.domain import models, schemas
from app.interfaces.deps import get_db, get_current_active_user, RoleChecker
from app.services import websocket_service
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def check_location_rate_limit(db: Session, volunteer_id, min_seconds: int = 1):
    """Rate limit: minimum 1 seconds between location updates (more permissive for real-time tracking)."""
    from sqlalchemy import and_
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=min_seconds)
    recent = (
        db.query(models.LocationTracking)
        .filter(
            and_(
                models.LocationTracking.volunteer_id == volunteer_id,
                models.LocationTracking.timestamp >= cutoff,
            )
        )
        .first()
    )
    if recent:
        return False
    return True


@router.post("/update-location")
def update_volunteer_location(
    body: schemas.LocationTrackingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Update volunteer location with donation context.
    No restrictive manual rate limit since frontend tracking has fallback poll intervals.
    """
    # Relax completely the rate limit so frontend doesn't throw 429 Too Many Requests
    # if not check_location_rate_limit(db, current_user.id, min_seconds=2):
    #     raise HTTPException(
    #         status_code=429,
    #         detail="Rate limit exceeded. Please wait before sending another location update.",
    #     )

    donation = None
    if body.donation_id:
        donation = (
            db.query(models.Donation)
            .filter(
                models.Donation.id == body.donation_id,
                models.Donation.volunteer_id == current_user.id,
            )
            .first()
        )
        if not donation:
            raise HTTPException(
                status_code=403, detail="You are not assigned to this donation"
            )

    location_record = models.LocationTracking(
        volunteer_id=current_user.id,
        donation_id=body.donation_id,
        latitude=body.latitude,
        longitude=body.longitude,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(location_record)

    profile = current_user.profile
    if profile:
        profile.current_lat = body.latitude
        profile.current_lng = body.longitude

    db.commit()
    db.refresh(location_record)

    if donation:
        broadcast_data = {
            "type": "LOCATION_UPDATE",
            "donation_id": str(donation.id),
            "volunteer_id": str(current_user.id),
            "latitude": body.latitude,
            "longitude": body.longitude,
            "timestamp": location_record.timestamp.isoformat(),
            "status": donation.status.value
            if hasattr(donation.status, "value")
            else str(donation.status),
        }
        # Use asyncio to run async broadcast function
        import asyncio

        try:
            asyncio.run(
                websocket_service.broadcast_to_donation(
                    str(donation.id), broadcast_data
                )
            )
        except Exception as e:
            logger.error(f"Broadcast error: {e}")

    return {
        "success": True,
        "message": "Location updated",
        "location_id": str(location_record.id),
    }


@router.post("/mark-picked-up")
def mark_picked_up(
    body: schemas.MarkPickedUpRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Mark donation as picked up. Triggers route switch from volunteer→donor to volunteer→NGO.
    """
    donation = (
        db.query(models.Donation)
        .filter(
            models.Donation.id == body.donation_id,
            models.Donation.volunteer_id == current_user.id,
        )
        .first()
    )

    if not donation:
        raise HTTPException(
            status_code=404, detail="Donation not found or not assigned to you"
        )

    # Convert status to lowercase string for comparison
    current_status = str(donation.status).lower() if donation.status else ""

    if current_status not in ["assigned", "in_progress", "claimed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot mark as picked_up from status: {donation.status}",
        )

    # Set status as string (database uses VARCHAR not enum)
    donation.status = "picked_up"
    donation.pickup_time = datetime.now(timezone.utc)

    if body.latitude is not None and body.longitude is not None:
        donation.pickup_latitude = body.latitude
        donation.pickup_longitude = body.longitude

    db.commit()
    db.refresh(donation)

    broadcast_data = {
        "type": "STATUS_CHANGED",
        "donation_id": str(donation.id),
        "new_status": "picked_up",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    # Use asyncio to run async broadcast function
    import asyncio

    try:
        asyncio.run(
            websocket_service.broadcast_to_donation(str(donation.id), broadcast_data)
        )
    except Exception as e:
        logger.error(f"Broadcast error: {e}")

    return {
        "success": True,
        "message": "Donation marked as picked up",
        "status": "picked_up",
    }


@router.get("/track/{donation_id}")
def track_donation_location(
    donation_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get current volunteer location for a donation.
    Accessible by donor, NGO, or assigned volunteer.
    """
    import uuid

    try:
        donation_uuid = uuid.UUID(donation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid donation ID")

    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_uuid).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    access_denied = True
    if (
        current_user.role == models.RoleEnum.DONOR
        and donation.donor_id == current_user.id
    ):
        access_denied = False
    elif (
        current_user.role == models.RoleEnum.NGO and donation.ngo_id == current_user.id
    ):
        access_denied = False
    elif (
        current_user.role == models.RoleEnum.VOLUNTEER
        and donation.volunteer_id == current_user.id
    ):
        access_denied = False

    if access_denied:
        raise HTTPException(
            status_code=403, detail="Not authorized to track this donation"
        )

    latest_location = (
        db.query(models.LocationTracking)
        .filter(models.LocationTracking.donation_id == donation_uuid)
        .order_by(models.LocationTracking.timestamp.desc())
        .first()
    )

    if not latest_location:
        return {"has_location": False, "message": "No location data available yet"}

    # Get NGO coordinates from profile
    ngo_lat = None
    ngo_lng = None
    ngo_name = None
    if donation.ngo_id:
        ngo_user = (
            db.query(models.User).filter(models.User.id == donation.ngo_id).first()
        )
        if ngo_user and ngo_user.profile:
            ngo_lat = ngo_user.profile.latitude
            ngo_lng = ngo_user.profile.longitude
            ngo_name = ngo_user.profile.name

    beneficiary_lat = None
    beneficiary_lng = None
    beneficiary_name = None
    if donation.beneficiary_id:
        beneficiary = db.query(models.Beneficiary).filter(models.Beneficiary.id == donation.beneficiary_id).first()
        if beneficiary:
            beneficiary_lat = beneficiary.latitude
            beneficiary_lng = beneficiary.longitude
            beneficiary_name = beneficiary.name

    return {
        "has_location": True,
        "volunteer_id": str(latest_location.volunteer_id),
        "latitude": latest_location.latitude,
        "longitude": latest_location.longitude,
        "timestamp": latest_location.timestamp.isoformat(),
        "donation_status": donation.status.value
        if hasattr(donation.status, "value")
        else str(donation.status),
        "ngo_lat": ngo_lat,
        "ngo_lng": ngo_lng,
        "ngo_name": ngo_name,
        "donor_lat": donation.latitude,
        "donor_lng": donation.longitude,
        "beneficiary_lat": beneficiary_lat,
        "beneficiary_lng": beneficiary_lng,
        "beneficiary_name": beneficiary_name,
        "is_distribution": donation.task_type == "distribution",
    }


@router.get("/latest/{donation_id}")
def get_latest_location(
    donation_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get latest location for a donation.
    Used for polling fallback when WebSocket is unavailable.
    Requires authentication.
    """
    import uuid

    try:
        donation_uuid = uuid.UUID(donation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid donation ID")

    latest_location = (
        db.query(models.LocationTracking)
        .filter(models.LocationTracking.donation_id == donation_uuid)
        .order_by(models.LocationTracking.timestamp.desc())
        .first()
    )

    if not latest_location:
        return {"has_location": False, "message": "No location data available"}

    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_uuid).first()
    )
    ngo_lat = None
    ngo_lng = None
    if donation and donation.ngo_id:
        ngo_user = (
            db.query(models.User).filter(models.User.id == donation.ngo_id).first()
        )
        if ngo_user and ngo_user.profile:
            ngo_lat = ngo_user.profile.latitude
            ngo_lng = ngo_user.profile.longitude
            
    beneficiary_lat = None
    beneficiary_lng = None
    if donation and donation.beneficiary_id:
        beneficiary = db.query(models.Beneficiary).filter(models.Beneficiary.id == donation.beneficiary_id).first()
        if beneficiary:
            beneficiary_lat = beneficiary.latitude
            beneficiary_lng = beneficiary.longitude

    return {
        "has_location": True,
        "latitude": latest_location.latitude,
        "longitude": latest_location.longitude,
        "timestamp": latest_location.timestamp.isoformat(),
        "ngo_lat": ngo_lat,
        "ngo_lng": ngo_lng,
        "beneficiary_lat": beneficiary_lat,
        "beneficiary_lng": beneficiary_lng,
        "is_distribution": donation.task_type == "distribution" if donation else False,
        "donation_status": donation.status.value
        if donation and hasattr(donation.status, "value")
        else (str(donation.status) if donation else None),
    }

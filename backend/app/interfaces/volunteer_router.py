from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.domain import models, schemas
from app.interfaces.deps import get_db, get_current_active_user, RoleChecker
from app.services import websocket_service, donation_service
import uuid
import logging
from datetime import datetime, timezone

from typing import List

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/available")
def get_available_volunteers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    if current_user.role != models.RoleEnum.NGO:
        return []

    volunteers = (
        db.query(models.User)
        .filter(
            models.User.role == models.RoleEnum.VOLUNTEER,
            models.User.ngo_id == current_user.id,
            models.User.volunteer_status.ilike("approved"),
            or_(
                models.User.availability.ilike("available"),
                models.User.availability.is_(None),
            ),
        )
        .all()
    )

    result = []
    for v in volunteers:
        profile = v.profile
        # Calculate distance if profile has location data
        distance = None
        if (
            profile
            and profile.current_lat is not None
            and profile.current_lng is not None
        ):
            ngo_profile = current_user.profile
            if ngo_profile and ngo_profile.latitude and ngo_profile.longitude:
                from app.services.donation_service import calculate_distance

                try:
                    km = calculate_distance(
                        ngo_profile.latitude,
                        ngo_profile.longitude,
                        profile.current_lat,
                        profile.current_lng,
                    )
                    distance = round(km, 1)
                except Exception:
                    distance = None

        result.append(
            {
                "id": str(v.id),
                "name": profile.name if profile else v.email.split("@")[0],
                "email": v.email,
                "availability": v.availability,
                "distance": distance if distance is not None else "N/A",
                "completed_deliveries": v.completed_deliveries or 0,
            }
        )

    logger.debug(
        "AVAILABLE VOLUNTEERS (NGO=%s): %s volunteers", current_user.id, len(result)
    )

    return result


@router.get("/pending")
def get_pending_volunteers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get all volunteers with 'pending' status assigned to this NGO.
    Uses the authenticated NGO's ID directly — no URL param needed.
    """
    if current_user.role != models.RoleEnum.NGO:
        return []
    volunteers = (
        db.query(models.User)
        .filter(
            models.User.role == models.RoleEnum.VOLUNTEER,
            models.User.volunteer_status.ilike("pending"),
            models.User.ngo_id == current_user.id,
        )
        .all()
    )

    result = []
    for v in volunteers:
        profile = v.profile
        result.append(
            {
                "id": str(v.id),
                "email": v.email,
                "created_at": v.created_at,
                "user": {"name": profile.name if profile else v.email.split("@")[0]},
                "phone": profile.phone if profile else "",
                "location": profile.address if profile else "",
            }
        )
    return result


@router.post("/approve/{id}")
def approve_volunteer(
    id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Approve a volunteer for this NGO.
    Returns simple success/message JSON for reliable frontend parsing.
    """
    if current_user.role != models.RoleEnum.NGO:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        vol_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid volunteer ID")

    volunteer = (
        db.query(models.User)
        .filter(
            models.User.id == vol_uuid,
            models.User.role == models.RoleEnum.VOLUNTEER,
            models.User.ngo_id == current_user.id,
        )
        .first()
    )

    if not volunteer:
        raise HTTPException(
            status_code=404, detail="Volunteer not found or not assigned to your NGO"
        )

    volunteer.volunteer_status = "approved"
    volunteer.status = "approved"
    volunteer.availability = "available"
    volunteer.is_active = True
    db.commit()
    db.refresh(volunteer)
    return {
        "success": True,
        "message": "Volunteer approved successfully",
        "volunteer_id": str(volunteer.id),
        "volunteer_status": "approved",
    }


@router.post("/reject/{id}")
def reject_volunteer(
    id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Reject a volunteer for this NGO.
    Returns simple success/message JSON for reliable frontend parsing.
    """
    if current_user.role != models.RoleEnum.NGO:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        vol_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid volunteer ID")

    volunteer = (
        db.query(models.User)
        .filter(
            models.User.id == vol_uuid,
            models.User.role == models.RoleEnum.VOLUNTEER,
            models.User.ngo_id == current_user.id,
        )
        .first()
    )

    if not volunteer:
        raise HTTPException(
            status_code=404, detail="Volunteer not found or not assigned to your NGO"
        )

    volunteer.volunteer_status = "rejected"
    volunteer.status = "rejected"
    db.commit()
    db.refresh(volunteer)
    return {
        "success": True,
        "message": "Volunteer rejected",
        "volunteer_id": str(volunteer.id),
        "volunteer_status": "rejected",
    }


@router.get("/my-deliveries")
def get_my_deliveries(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Return all deliveries assigned to the volunteer, including donation details.
    """
    if current_user.role != models.RoleEnum.VOLUNTEER:
        return []

    from sqlalchemy.orm import joinedload

    deliveries = (
        db.query(models.Delivery)
        .options(joinedload(models.Delivery.donation))
        .filter(models.Delivery.volunteer_id == current_user.id)
        .all()
    )

    otp_rotated = False
    for delivery in deliveries:
        if delivery.donation and donation_service.auto_rotate_expired_pickup_otp(
            db, delivery.donation
        ):
            otp_rotated = True
    if otp_rotated:
        db.commit()
        for delivery in deliveries:
            db.refresh(delivery)
            if delivery.donation:
                db.refresh(delivery.donation)

    ngo_cache = {}

    def get_ngo_destination(ngo_id):
        if not ngo_id:
            return {
                "ngo_name": None,
                "ngo_latitude": None,
                "ngo_longitude": None,
                "ngo_address": None,
            }

        key = str(ngo_id)
        if key in ngo_cache:
            return ngo_cache[key]

        ngo_user = db.query(models.User).filter(models.User.id == ngo_id).first()
        ngo_profile = ngo_user.profile if ngo_user else None

        ngo_cache[key] = {
            "ngo_name": (
                ngo_profile.name
                if ngo_profile and ngo_profile.name
                else (ngo_user.name or ngo_user.email.split("@")[0])
                if ngo_user
                else None
            ),
            "ngo_latitude": ngo_profile.latitude if ngo_profile else None,
            "ngo_longitude": ngo_profile.longitude if ngo_profile else None,
            "ngo_address": ngo_profile.address if ngo_profile else None,
        }
        return ngo_cache[key]

    result = []
    for d in deliveries:
        ngo_destination = get_ngo_destination(d.donation.ngo_id if d.donation else None)
        
        beneficiary_name = None
        dropoff_latitude = None
        dropoff_longitude = None
        if d.donation and d.donation.beneficiary_id:
            beneficiary = db.query(models.Beneficiary).filter(models.Beneficiary.id == d.donation.beneficiary_id).first()
            if beneficiary:
                beneficiary_name = beneficiary.name
                dropoff_latitude = beneficiary.latitude
                dropoff_longitude = beneficiary.longitude
                
        otp_meta = (
            donation_service.get_donation_otp_metadata(d.donation) if d.donation else {}
        )
        donation_status = (
            d.donation.status.value
            if d.donation and hasattr(d.donation.status, "value")
            else str(d.donation.status).lower()
            if d.donation
            else "unknown"
        )
        otp_generated = bool(
            d.donation and d.donation.otp_code and not d.donation.otp_verified
        )
        otp_verified = bool(d.donation.otp_verified) if d.donation else False
        otp_cooldown_remaining = otp_meta.get("otp_resend_available_in_seconds", 0)

        # User requested fields: donation_id, food_type, quantity, status, pickup_location
        # Fallback to delivery defaults if donation is missing (should not happen)

        # Use delivery status if available, otherwise fall back to donation status
        delivery_status = (
            d.status.value.lower()
            if d.status and hasattr(d.status, "value")
            else str(d.status).lower()
            if d.status
            else donation_status
        )

        d_dict = {
            "donation_id": str(d.donation.id)
            if d.donation
            else (str(d.donation_id) if d.donation_id else None),
            "food_type": d.donation.food_type if d.donation else "Unknown",
            "quantity": d.donation.quantity if d.donation else 0,
            "status": delivery_status,
            "delivery_status": delivery_status,
            "latitude": d.donation.latitude if d.donation else None,
            "longitude": d.donation.longitude if d.donation else None,
            "pickup_latitude": d.donation.pickup_latitude if d.donation else None,
            "pickup_longitude": d.donation.pickup_longitude if d.donation else None,
            "pickup_location": (d.donation.pickup_location or d.donation.pickup_address)
            if d.donation
            else "Unknown",
            # Backward-compatible alias expected by older UI cards
            "pickup_address": (d.donation.pickup_location or d.donation.pickup_address)
            if d.donation
            else "Unknown",
            # Delivery model stores assigned_at/completed_at, not created_at
            "created_at": d.assigned_at.isoformat() if d.assigned_at else None,
            # Keep OTP value private; only expose generation state to UI.
            "otp_generated": otp_generated,
            "otp_verified": otp_verified,
            "otp_generated_at": otp_meta.get("otp_generated_at"),
            "otp_expires_at": otp_meta.get("otp_expires_at"),
            "otp_seconds_remaining": otp_meta.get("otp_seconds_remaining"),
            "otp_validity_seconds": otp_meta.get("otp_validity_seconds"),
            "otp_resend_available_in_seconds": otp_cooldown_remaining,
            "otp_regenerate_cooldown_seconds": otp_meta.get(
                "otp_regenerate_cooldown_seconds"
            ),
            "otp_can_regenerate": (
                donation_status == "assigned"
                and not otp_verified
                and otp_cooldown_remaining == 0
            ),
            "volunteer_reached_donor": bool(d.donation.volunteer_reached_donor)
            if d.donation
            else False,
            "donation_received": bool(d.donation.donation_received)
            if d.donation
            else False,
            "delivery_status": d.donation.delivery_status if d.donation else None,
            "ngo_name": ngo_destination["ngo_name"],
            "ngo_latitude": ngo_destination["ngo_latitude"],
            "ngo_longitude": ngo_destination["ngo_longitude"],
            "ngo_address": ngo_destination["ngo_address"],
            "is_distribution": d.donation.task_type == "distribution" if d.donation else False,
            "task_type": d.donation.task_type if d.donation else None,
            "beneficiary_name": beneficiary_name,
            "dropoff_latitude": dropoff_latitude,
            "dropoff_longitude": dropoff_longitude,
        }

        # Keep backwards compatibility fields just in case it breaks older parts of volunteer dashboard
        d_dict["id"] = str(d.id)
        if d.donation:
            d_dict["donation"] = {
                "id": str(d.donation.id),
                "food_type": d.donation.food_type,
                "quantity": d.donation.quantity,
                "status": d.donation.status.value
                if hasattr(d.donation.status, "value")
                else str(d.donation.status),
                "pickup_address": d.donation.pickup_address,
                "pickup_location": d.donation.pickup_location
                or d.donation.pickup_address,
                "ngo_name": ngo_destination["ngo_name"],
                "ngo_latitude": ngo_destination["ngo_latitude"],
                "ngo_longitude": ngo_destination["ngo_longitude"],
                "ngo_address": ngo_destination["ngo_address"],
                "created_at": d.donation.created_at,
            }
        result.append(d_dict)
    return result


@router.post("/update-location")
def update_location(
    body: schemas.VolunteerLocationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Update live location of the volunteer.
    """
    profile = current_user.profile
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.current_lat = body.latitude
    profile.current_lng = body.longitude

    # Track history
    history = models.VolunteerLocation(
        volunteer_id=current_user.id, latitude=body.latitude, longitude=body.longitude
    )
    db.add(history)

    db.commit()
    return {"status": "location updated"}


@router.post("/status")
def update_status(
    data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    vol = db.query(models.User).filter(models.User.id == current_user.id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    incoming = data.get("availability")
    if incoming is None:
        incoming = data.get("status")
    if isinstance(incoming, bool):
        incoming = "available" if incoming else "busy"
    incoming = (incoming or "").strip().lower()
    if incoming not in {"available", "busy"}:
        raise HTTPException(
            status_code=400,
            detail="availability must be 'available' or 'busy'",
        )

    vol.availability = incoming
    db.commit()
    db.refresh(vol)

    background_tasks.add_task(
        websocket_service.broadcast,
        {
            "type": "STATUS_UPDATE",
            "volunteer_id": str(vol.id),
            "availability": vol.availability,
        },
    )

    return {"success": True, "availability": vol.availability}


@router.get("/me/status")
def get_my_volunteer_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get current volunteer's approval status.
    Returns volunteer_status, availability, and is_online (based on recent location update).
    """
    if current_user.role != models.RoleEnum.VOLUNTEER:
        return {
            "status": "not_volunteer",
            "volunteer_status": None,
            "availability": None,
            "is_online": False,
        }

    is_online = False
    if current_user.availability == "available":
        recent_location = (
            db.query(models.VolunteerLocation)
            .filter(models.VolunteerLocation.volunteer_id == current_user.id)
            .order_by(models.VolunteerLocation.timestamp.desc())
            .first()
        )
        if recent_location and recent_location.timestamp:
            from datetime import timedelta

            ts = recent_location.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            time_diff = datetime.now(timezone.utc) - ts
            is_online = time_diff.total_seconds() < 300

    return {
        "status": current_user.status or current_user.volunteer_status or "pending",
        "volunteer_status": current_user.volunteer_status or "pending",
        "availability": current_user.availability or "available",
        "is_online": is_online,
        "completed_deliveries": current_user.completed_deliveries or 0,
        "rating": round(current_user.rating or 5.0, 1),
        "ngo_id": str(current_user.ngo_id) if current_user.ngo_id else None,
    }


def calculate_level(completed: int) -> dict:
    """Calculate volunteer level based on completed deliveries."""
    if completed >= 50:
        return {"level": "Gold", "next_level": None, "remaining": 0, "target": 50}
    elif completed >= 25:
        return {
            "level": "Silver",
            "next_level": "Gold",
            "remaining": 50 - completed,
            "target": 50,
        }
    elif completed >= 10:
        return {
            "level": "Bronze",
            "next_level": "Silver",
            "remaining": 25 - completed,
            "target": 25,
        }
    else:
        return {
            "level": "Bronze",
            "next_level": "Bronze",
            "remaining": 10 - completed,
            "target": 10,
        }


@router.get("/dashboard-summary")
def get_volunteer_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Get volunteer dashboard summary: total deliveries, completed, success rate, level.
    """
    total = (
        db.query(models.Delivery)
        .filter(models.Delivery.volunteer_id == current_user.id)
        .count()
    )

    # Use enum for completed comparison
    completed = (
        db.query(models.Delivery)
        .filter(
            models.Delivery.volunteer_id == current_user.id,
            models.Delivery.status == models.DeliveryStatusEnum.DELIVERED,
        )
        .count()
    )

    success_rate = round((completed / total * 100), 1) if total > 0 else 0
    level_info = calculate_level(completed)

    return {
        "total_deliveries": total,
        "completed": completed,
        "success_rate": success_rate,
        "level": level_info["level"],
        "next_level": level_info["next_level"],
        "remaining": level_info["remaining"],
        "target": level_info["target"],
        "rating": round(current_user.rating or 5.0, 1),
    }


@router.get("/rewards")
def get_volunteer_rewards(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Get volunteer rewards and points.
    Points = completed deliveries * 10
    """
    completed = current_user.completed_deliveries or 0
    points = completed * 10
    level_info = calculate_level(completed)

    return {
        "points": points,
        "level": level_info["level"],
        "next_level": level_info["next_level"],
        "remaining": level_info["remaining"],
        "target": level_info["target"],
        "completed": completed,
    }


@router.get("/active-delivery")
def get_active_delivery(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Get the currently active delivery for the volunteer.
    Returns only non-completed deliveries (not delivered, not failed).
    """
    from sqlalchemy.orm import joinedload
    from app.domain.models import DeliveryStatusEnum

    delivery = (
        db.query(models.Delivery)
        .options(joinedload(models.Delivery.donation))
        .filter(
            models.Delivery.volunteer_id == current_user.id,
            models.Delivery.status.notin_(
                [DeliveryStatusEnum.DELIVERED, DeliveryStatusEnum.FAILED]
            ),
        )
        .order_by(models.Delivery.assigned_at.desc())
        .first()
    )

    if not delivery or not delivery.donation:
        return {"has_active": False, "delivery": None}

    donation = delivery.donation

    # --- Dynamic Routing Logic (Pickup vs Distribution) ---
    pickup_location = donation.pickup_location or donation.pickup_address
    pickup_latitude = donation.pickup_latitude or donation.latitude
    pickup_longitude = donation.pickup_longitude or donation.longitude
    
    # Default dropoff is NGO (for pickup leg)
    dropoff_location = None
    dropoff_latitude = None
    dropoff_longitude = None

    ngo_user = (
        db.query(models.User).filter(models.User.id == donation.ngo_id).first()
    )
    if ngo_user and ngo_user.profile:
        dropoff_location = ngo_user.profile.address
        dropoff_latitude = ngo_user.profile.latitude
        dropoff_longitude = ngo_user.profile.longitude

    # If it's a distribution leg (has beneficiary assigned)
    beneficiary_name = None
    if donation.beneficiary_id:
        beneficiary = db.query(models.Beneficiary).filter(models.Beneficiary.id == donation.beneficiary_id).first()
        if beneficiary:
            beneficiary_name = beneficiary.name
            # For distribution leg: Pickup is from NGO, Dropoff is at Beneficiary
            if ngo_user and ngo_user.profile:
                pickup_location = ngo_user.profile.address
                pickup_latitude = ngo_user.profile.latitude
                pickup_longitude = ngo_user.profile.longitude
            
            dropoff_location = beneficiary.address
            dropoff_latitude = beneficiary.latitude
            dropoff_longitude = beneficiary.longitude

    return {
        "has_active": True,
        "delivery": {
            "id": str(delivery.id),
            "donation_id": str(donation.id),
            "is_distribution": bool(donation.beneficiary_id),
            "beneficiary_name": beneficiary_name,
            "food_type": donation.food_type,
            "quantity": donation.quantity,
            "pickup_location": pickup_location,
            "pickup_latitude": pickup_latitude,
            "pickup_longitude": pickup_longitude,
            "dropoff_location": dropoff_location,
            "dropoff_latitude": dropoff_latitude,
            "dropoff_longitude": dropoff_longitude,
            "status": donation.delivery_status or "pending",
            "assigned_at": delivery.assigned_at.isoformat()
            if delivery.assigned_at
            else None,
            "created_at": donation.created_at.isoformat()
            if donation.created_at
            else None,
        },
    }


@router.post("/update-delivery-status")
def update_delivery_status(
    data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Update delivery status: picked, in_transit, delivered.
    """
    delivery_id = data.get("delivery_id")
    new_status = data.get("status")

    if not delivery_id or not new_status:
        raise HTTPException(status_code=400, detail="delivery_id and status required")

    if new_status not in ["picked", "in_transit", "delivered"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    try:
        delivery_uuid = uuid.UUID(delivery_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid delivery ID")

    delivery = (
        db.query(models.Delivery)
        .filter(
            models.Delivery.id == delivery_uuid,
            models.Delivery.volunteer_id == current_user.id,
        )
        .first()
    )

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    if not delivery.donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    donation = delivery.donation

    if new_status == "picked":
        donation.delivery_status = "picked_up"
        donation.volunteer_reached_donor = True
    elif new_status == "in_transit":
        donation.delivery_status = "in_progress"
    elif new_status == "delivered":
        donation.delivery_status = "completed"
        donation.donation_received = True
        delivery.status = "completed"
        current_user.completed_deliveries = (current_user.completed_deliveries or 0) + 1

    db.commit()
    db.refresh(donation)
    db.refresh(delivery)
    db.refresh(current_user)

    background_tasks.add_task(
        websocket_service.broadcast,
        {
            "type": "DELIVERY_STATUS_UPDATE",
            "delivery_id": str(delivery.id),
            "donation_id": str(donation.id),
            "status": donation.delivery_status,
            "volunteer_id": str(current_user.id),
        },
    )

    return {"success": True, "status": donation.delivery_status}


@router.post("/complete-distribution")
def complete_distribution(
    data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Volunteer completes the distribution stage by providing the Beneficiary OTP.
    """
    donation_id = data.get("donation_id")
    otp = data.get("otp")

    if not donation_id:
        raise HTTPException(status_code=400, detail="donation_id required")

    try:
        donation_uuid = uuid.UUID(donation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid donation ID")

    donation = (
        db.query(models.Donation)
        .filter(models.Donation.id == donation_uuid)
        .first()
    )

    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if donation.volunteer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not assigned to this donation")

    if donation.task_type != "distribution":
        raise HTTPException(status_code=400, detail="This task is not a distribution task")

    # OTP verification removed as per user request for second-leg logistics
    # if donation.distribution_otp != str(otp).strip():
    #     raise HTTPException(status_code=400, detail="Invalid Beneficiary OTP")

    donation.distribution_status = "completed"
    donation.distribution_otp = None  # Clear OTP after verification
    donation.status = models.DonationStatusEnum.COMPLETED
    donation.delivery_status = "completed"

    # Set volunteer to available
    current_user.availability = "available"
    current_user.completed_deliveries = (current_user.completed_deliveries or 0) + 1
    
    # Optional: also mark the delivery record as delivered
    delivery = db.query(models.Delivery).filter(
        models.Delivery.donation_id == donation_uuid,
        models.Delivery.volunteer_id == current_user.id
    ).first()
    if delivery:
        delivery.status = models.DeliveryStatusEnum.DELIVERED

    db.commit()

    return {"success": True, "message": "Distribution completed successfully"}

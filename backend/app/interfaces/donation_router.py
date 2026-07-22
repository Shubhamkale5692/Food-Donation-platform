from typing import List, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.domain import schemas, models
from app.services import donation_service, websocket_service
from app.interfaces.deps import get_db, get_current_active_user, RoleChecker
from app.core.constants import (
    CERTIFICATE_MIN_DONATIONS,
    OTP_VALIDITY_MINUTES,
    TRUST_SCORE_INCREMENT,
    TRUST_SCORE_MAX,
)
from datetime import datetime, timezone
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=schemas.DonationResponse)
def create_donation(
    *,
    db: Session = Depends(get_db),
    donation_in: schemas.DonationCreate,
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.DONOR])),
):
    """
    Create a new donation. Only DONOR role should ideally access this.
    """
    created = donation_service.create_donation(
        db=db, donation_in=donation_in, donor_id=current_user.id
    )

    # Trigger background AI check (non-critical)
    try:
        from app.workers.tasks import process_donation_freshness

        process_donation_freshness.delay(str(created.id))
    except Exception as celery_err:
        logging.getLogger(__name__).warning(
            "Celery task dispatch failed (broker may be unavailable): %s", celery_err
        )

    return created


@router.post("/location")
def save_donation_location(
    body: schemas.DonationLocationPayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.DONOR])),
):
    """
    Feature 1 API Endpoint: POST /api/donation/location
    Saves the requested location for a donation pick-up.
    """
    if current_user.profile:
        current_user.profile.latitude = body.latitude
        current_user.profile.longitude = body.longitude
        current_user.profile.address = body.full_address
        db.commit()
    return {
        "message": "Pickup location saved successfully",
        "saved_location": {
            "pickup_latitude": body.latitude,
            "pickup_longitude": body.longitude,
            "pickup_address": body.full_address,
        },
    }


@router.get("/", response_model=List[schemas.DonationResponse])
def read_donations(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Retrieve donations.
    For DONOR role: returns all their own donations (including cancelled).
    For NGO: returns all pending globally AND their own accepted/assigned.
    For VOLUNTEER: returns only assigned via Delivery table.
    """
    logger.debug(
        "GET /donations called by user=%s role=%s", current_user.id, current_user.role
    )
    try:
        ngo_id = current_user.id if current_user.role == models.RoleEnum.NGO else None
        volunteer_id = (
            current_user.id if current_user.role == models.RoleEnum.VOLUNTEER else None
        )
        donor_id = (
            current_user.id if current_user.role == models.RoleEnum.DONOR else None
        )
        donations = donation_service.get_donations(
            db,
            skip=skip,
            limit=limit,
            ngo_id=ngo_id,
            volunteer_id=volunteer_id,
            status_filter=status,
            donor_id=donor_id,
            role=current_user.role.value if current_user.role else None,
        )
        return donations
    except Exception as e:
        logger.exception("Error in read_donations: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.get("/pending", response_model=List[schemas.DonationResponse])
def get_pending_donations(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get only pending donations globally.
    DO NOT filter by NGO. All NGOs must see pending donations.
    """
    logger.debug(
        "GET /donations/pending called by user=%s role=%s",
        current_user.id,
        current_user.role,
    )
    try:
        donations = donation_service.get_donations(
            db,
            skip=skip,
            limit=limit,
            status_filter=models.DonationStatusEnum.PENDING.value,
            role="GLOBAL_PENDING",
        )
        return donations
    except Exception as e:
        logger.exception("Error in get_pending_donations: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.get("/active", response_model=List[schemas.DonationResponse])
def get_active_donations(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get active donations: Pending, Accepted, Assigned, In-Transit.
    """
    donations = donation_service.get_active_donations(db, skip=skip, limit=limit)

    otp_rotated = False
    for donation in donations:
        if donation_service.auto_rotate_expired_pickup_otp(db, donation):
            otp_rotated = True
    if otp_rotated:
        db.commit()
        for donation in donations:
            db.refresh(donation)

    viewer_role = str(current_user.role.value if current_user.role else "").upper()
    for donation in donations:
        donation_service.apply_otp_view_for_donation(
            donation,
            viewer_role=viewer_role,
            viewer_user_id=current_user.id,
        )

    return donations


@router.get("/assigned", response_model=List[schemas.DonationResponse])
def get_assigned_donations(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get donations assigned to the current volunteer (status = ASSIGNED only).
    """
    if current_user.role != models.RoleEnum.VOLUNTEER:
        raise HTTPException(
            status_code=403, detail="Only volunteers can access this endpoint"
        )
    from sqlalchemy import and_

    donations = (
        db.query(models.Donation)
        .join(models.Delivery, models.Delivery.donation_id == models.Donation.id)
        .filter(
            and_(
                models.Donation.volunteer_id == current_user.id,
                models.Donation.status.in_(
                    [
                        models.DonationStatusEnum.ASSIGNED,
                        models.DonationStatusEnum.IN_PROGRESS,
                    ]
                ),
            )
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    otp_rotated = False
    for donation in donations:
        if donation_service.auto_rotate_expired_pickup_otp(db, donation):
            otp_rotated = True
    if otp_rotated:
        db.commit()
        for donation in donations:
            db.refresh(donation)

    for donation in donations:
        donation_service.apply_otp_view_for_donation(
            donation,
            viewer_role="VOLUNTEER",
            viewer_user_id=current_user.id,
        )

    return donations


@router.put("/{donation_id}/status", response_model=schemas.DonationResponse)
def update_donation_status(
    *,
    db: Session = Depends(get_db),
    donation_id: uuid.UUID,
    body: schemas.DonationStatusUpdate,
    current_user: models.User = Depends(
        RoleChecker(
            [models.RoleEnum.NGO, models.RoleEnum.ADMIN, models.RoleEnum.VOLUNTEER]
        )
    ),
):
    """
    Update donation status.
    - NGO / Admin: can Accept or Cancel
    - Volunteer: can mark In-Transit or Completed
    """
    donation = donation_service.update_donation_status(
        db=db,
        donation_id=donation_id,
        status=body.status,
        actor_id=current_user.id,
        actor_role=current_user.role,
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")
    return donation


@router.post("/{donation_id}/claim", response_model=schemas.DonationResponse)
def claim_donation(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.NGO])),
):
    """
    NGO claims a donation. Only works when donation status is PENDING.
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="NGO not verified by admin yet. Contact admin to verify your account.",
        )

    try:
        donation = donation_service.claim_donation(db, donation_id, current_user.id)
    except Exception as e:
        logger.exception("Error in claim_donation: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="An error occurred while accepting the donation: " + str(e),
        )

    if not donation:
        d = donation_service.get_donation_by_id(db, donation_id)
        if not d:
            raise HTTPException(status_code=404, detail="Donation not found")
        if d.status == models.DonationStatusEnum.ACCEPTED:
            raise HTTPException(
                status_code=400,
                detail="This donation has already been accepted by an NGO.",
            )
        raise HTTPException(
            status_code=400,
            detail="Only Pending donations can be accepted. Current status: "
            + d.status.value,
        )
    return donation


@router.post("/cancel/{donation_id}")
def cancel_donation(
    donation_id: uuid.UUID,
    body: Optional[schemas.CancelDonationRequest] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.DONOR])),
):
    """
    Donor cancels their own donation.
    Accepts optional cancel_reason in the JSON body.
    Frees any assigned volunteer and deletes the delivery record.
    Returns {success, message, donation}.
    """
    reason = body.cancel_reason if body and body.cancel_reason else None
    donation = donation_service.cancel_donation(
        db=db,
        donation_id=donation_id,
        donor_id=current_user.id,
        cancel_reason=reason,
    )
    if not donation:
        d = donation_service.get_donation_by_id(db, donation_id)
        if not d:
            raise HTTPException(status_code=404, detail="Donation not found")
        if d.donor_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You can only cancel your own donations"
            )
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel donation with status '{d.status.value}'. Only pending, accepted, or assigned donations can be cancelled.",
        )
    return {
        "success": True,
        "message": "Donation cancelled successfully",
        "donation": {
            "id": str(donation.id),
            "status": donation.status.value,
            "cancel_reason": donation.cancel_reason,
        },
    }


@router.post("/{donation_id}/assign-volunteer", response_model=schemas.DeliveryResponse)
def assign_volunteer(
    donation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.NGO])),
    volunteer_id: Optional[uuid.UUID] = None,
):
    """
    NGO assigns a volunteer to a claimed donation (Manual Assignment).
    """
    log = logging.getLogger("foodbridge.assign_route")

    if not volunteer_id:
        raise HTTPException(status_code=400, detail="volunteer_id is required")

    donation = donation_service.get_donation_by_id(db, donation_id)
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if donation.status != models.DonationStatusEnum.ACCEPTED:
        raise HTTPException(
            status_code=400,
            detail=f"Donation is already '{donation.status.value}' — cannot assign another volunteer.",
        )

    vol = db.query(models.User).filter(models.User.id == volunteer_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    # Bug 4 Fix: Explicit str cast to prevent crashes on non-string inputs
    vol_status = str(vol.volunteer_status or "").strip().lower()
    if vol_status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Volunteer is not approved (volunteer_status={vol.volunteer_status}). Only approved volunteers can be assigned.",
        )
    # Only block if EXPLICITLY marked busy
    if str(vol.availability or "").strip().lower() == "busy":
        raise HTTPException(
            status_code=400,
            detail="Selected volunteer is currently busy and cannot be assigned.",
        )

    delivery = donation_service.assign_volunteer(
        db, donation_id, current_user.id, volunteer_id
    )
    if not delivery:
        raise HTTPException(
            status_code=400,
            detail="No available volunteers at the moment. Please ensure volunteers are approved for this NGO.",
        )
    log.info("Volunteer assigned to donation %s", donation_id)
    background_tasks.add_task(
        websocket_service.broadcast,
        {
            "type": "NEW_ASSIGNMENT",
            "donation_id": str(donation_id),
            "volunteer_id": str(delivery.volunteer_id),
        },
    )
    return delivery


@router.post("/{donation_id}/generate-otp")
def generate_otp(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Volunteer requests OTP generation. It sets a 6 digit code.
    """
    if current_user.role != models.RoleEnum.VOLUNTEER:
        raise HTTPException(status_code=403, detail="Only volunteers can generate OTP")

    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if donation.volunteer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not assigned to this donation")
    if donation.status not in [
        models.DonationStatusEnum.ASSIGNED,
        models.DonationStatusEnum.CLAIMED,
    ]:
        raise HTTPException(
            status_code=400,
            detail="OTP can only be generated for donations in assigned or claimed state",
        )
    if donation.otp_verified:
        raise HTTPException(
            status_code=400,
            detail="OTP is already verified for this donation",
        )

    delivery = (
        db.query(models.Delivery)
        .filter(
            models.Delivery.donation_id == donation_id,
            models.Delivery.volunteer_id == current_user.id,
        )
        .first()
    )
    if not delivery:
        raise HTTPException(
            status_code=404, detail="Delivery not found for this assigned donation"
        )

    if delivery.status != models.DeliveryStatusEnum.ASSIGNED:
        raise HTTPException(
            status_code=400,
            detail="OTP can only be generated for deliveries in assigned state",
        )

    had_existing_otp = bool(donation.otp_code)
    _, cooldown_remaining = donation_service.create_or_regenerate_pickup_otp(
        db, donation, bypass_cooldown=False
    )
    if cooldown_remaining > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {cooldown_remaining} seconds before regenerating OTP.",
        )

    db.commit()
    db.refresh(donation)
    db.refresh(delivery)

    otp_meta = donation_service.get_donation_otp_metadata(donation)

    return {
        "message": "OTP regenerated and sent to donor dashboard."
        if had_existing_otp
        else "OTP generated and sent to donor dashboard.",
        "success": True,
        "donation_id": str(donation_id),
        "delivery_id": str(delivery.id),
        "expires_in_minutes": OTP_VALIDITY_MINUTES,
        "otp_generated_at": otp_meta["otp_generated_at"],
        "otp_expires_at": otp_meta["otp_expires_at"],
        "otp_seconds_remaining": otp_meta["otp_seconds_remaining"],
        "otp_resend_available_in_seconds": otp_meta["otp_resend_available_in_seconds"],
        "otp_regenerate_cooldown_seconds": otp_meta["otp_regenerate_cooldown_seconds"],
    }


@router.post("/{donation_id}/verify-otp", response_model=schemas.DeliveryResponse)
def verify_otp(
    donation_id: uuid.UUID,
    body: schemas.OTPVerify,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Verify OTP for donation pickup. OTP is valid for 10 minutes only.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")
    if donation.volunteer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not assigned to this donation")
    if donation.status != models.DonationStatusEnum.ASSIGNED:
        raise HTTPException(
            status_code=400,
            detail="OTP verification is allowed only for assigned donations",
        )
    if not donation.otp_code:
        raise HTTPException(
            status_code=400,
            detail="No active OTP found. Generate OTP first.",
        )

    if donation_service.auto_rotate_expired_pickup_otp(db, donation):
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"OTP expired. A new OTP was auto-generated and sent to donor dashboard (valid for {OTP_VALIDITY_MINUTES} minutes).",
        )

    delivery = donation_service.verify_delivery_otp(
        db, donation_id=donation_id, otp=body.otp, volunteer_id=current_user.id
    )
    if not delivery:
        cooldown_remaining = donation_service.get_otp_resend_available_in_seconds(
            donation
        )
        if cooldown_remaining > 0:
            detail = (
                f"Invalid OTP. You can regenerate OTP in {cooldown_remaining} seconds."
            )
        else:
            detail = "Invalid OTP. You can regenerate OTP now."
        raise HTTPException(
            status_code=400,
            detail=detail,
        )

    background_tasks.add_task(
        websocket_service.broadcast,
        {"type": "OTP_VERIFIED", "donation_id": str(donation_id)},
    )

    return delivery


@router.get("/{donation_id}/track")
def track_delivery(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Retrieve live location of the volunteer for a specific donation.
    Accessible by donor owner, assigned NGO, assigned volunteer, or admin
    after volunteer has clicked 'Received Donation'.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    delivery = (
        db.query(models.Delivery)
        .filter(models.Delivery.donation_id == donation_id)
        .first()
    )

    user_role = (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else str(current_user.role or "")
    )
    can_access_tracking = (
        user_role.upper() == "ADMIN"
        or donation.donor_id == current_user.id
        or donation.ngo_id == current_user.id
        or (delivery and delivery.volunteer_id == current_user.id)
    )
    if not can_access_tracking:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to view tracking for this donation",
        )

    if not donation.donation_received:
        raise HTTPException(
            status_code=403,
            detail="Live tracking will be available after volunteer receives the donation",
        )

    if not delivery:
        raise HTTPException(
            status_code=404, detail="Delivery not found for this donation"
        )

    volunteer = (
        db.query(models.User).filter(models.User.id == delivery.volunteer_id).first()
    )
    if not volunteer or not volunteer.profile:
        raise HTTPException(status_code=404, detail="Volunteer profile not found")

    ngo_profile = None
    ngo_name = None
    if donation.ngo_id:
        ngo_user = (
            db.query(models.User).filter(models.User.id == donation.ngo_id).first()
        )
        if ngo_user:
            ngo_profile = ngo_user.profile
            ngo_name = (
                ngo_profile.name
                if ngo_profile and ngo_profile.name
                else (ngo_user.name or ngo_user.email.split("@")[0])
            )

    return {
        "donation_id": str(donation.id),
        "latitude": volunteer.profile.current_lat,
        "longitude": volunteer.profile.current_lng,
        "status": delivery.status.value
        if hasattr(delivery.status, "value")
        else str(delivery.status),
        "live_tracking_enabled": donation.donation_received,
        "pickup_latitude": donation.pickup_latitude or donation.latitude,
        "pickup_longitude": donation.pickup_longitude or donation.longitude,
        "pickup_location": donation.pickup_location or donation.pickup_address,
        "ngo_name": ngo_name,
        "ngo_latitude": ngo_profile.latitude if ngo_profile else None,
        "ngo_longitude": ngo_profile.longitude if ngo_profile else None,
        "ngo_address": ngo_profile.address if ngo_profile else None,
    }


@router.put("/location", response_model=schemas.ProfileResponse)
def update_location(
    body: schemas.LocationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Volunteer periodically updates their live GPS coordinates.
    """
    profile = donation_service.update_volunteer_location(
        db, volunteer_id=current_user.id, lat=body.latitude, lng=body.longitude
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Volunteer profile not found")
    return profile


@router.get("/my-donations/certificate")
def get_donor_certificate(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.DONOR])),
):
    """
    Verify if donor is eligible for a certificate (count >= CERTIFICATE_MIN_DONATIONS).
    """
    donation_count = (
        db.query(models.Donation)
        .filter(
            models.Donation.donor_id == current_user.id,
            models.Donation.status == models.DonationStatusEnum.COMPLETED,
        )
        .count()
    )

    if donation_count >= CERTIFICATE_MIN_DONATIONS:
        return {
            "eligible": True,
            "count": donation_count,
            "message": "Congratulations! You have earned a certificate for your contributions.",
        }
    else:
        return {
            "eligible": False,
            "count": donation_count,
            "message": f"You need {CERTIFICATE_MIN_DONATIONS - donation_count} more successful donations to earn a certificate.",
        }


@router.post("/{donation_id}/reached-location")
def volunteer_reached_location(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Volunteer clicks 'Reached Location' when they arrive at donor's location.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if donation.volunteer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not assigned to this donation")

    if not donation.otp_verified:
        raise HTTPException(
            status_code=400, detail="Please verify OTP first before marking as reached"
        )

    donation.volunteer_reached_donor = True
    db.commit()

    return {
        "success": True,
        "message": "You have reached the donor's location. Please collect the donation.",
        "donation_id": str(donation_id),
    }


@router.post("/{donation_id}/receive-donation")
def volunteer_receive_donation(
    donation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Volunteer clicks 'Received Donation' after receiving food from donor.
    This enables live location sharing with NGO and Donor.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if donation.volunteer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not assigned to this donation")

    if not donation.volunteer_reached_donor:
        donation.volunteer_reached_donor = True

    donation.donation_received = True
    donation.delivery_status = "in_transit"
    donation.status = models.DonationStatusEnum.IN_PROGRESS

    delivery = (
        db.query(models.Delivery)
        .filter(models.Delivery.donation_id == donation_id)
        .first()
    )
    if delivery:
        delivery.status = models.DeliveryStatusEnum.IN_PROGRESS

    db.commit()

    background_tasks.add_task(
        websocket_service.broadcast,
        {
            "type": "DONATION_RECEIVED",
            "donation_id": str(donation_id),
            "volunteer_id": str(current_user.id),
        },
    )

    return {
        "success": True,
        "message": "Donation received. Live tracking enabled for NGO/Donor.",
        "donation_id": str(donation_id),
        "live_tracking_enabled": True,
    }


@router.post("/{donation_id}/complete")
def complete_donation(
    donation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Volunteer marks donation as COMPLETED.
    Only allowed if status is 'picked_up'.
    Completes the delivery lifecycle.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if donation.volunteer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not assigned to this donation")

    if donation.status != models.DonationStatusEnum.PICKED_UP:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot complete donation. Current status: {donation.status.value}. Must be 'picked_up' first.",
        )

    # Use centralized service to complete donation (handles status, delivery, duration, trust scores, etc.)
    donation = donation_service.update_donation_status(
        db=db,
        donation_id=donation_id,
        status=models.DonationStatusEnum.COMPLETED,
        actor_id=current_user.id,
        actor_role=models.RoleEnum.VOLUNTEER,
    )
    if not donation:
        raise HTTPException(
            status_code=404, detail="Donation not found after completion"
        )

    volunteer = db.query(models.User).filter(models.User.id == current_user.id).first()

    background_tasks.add_task(
        websocket_service.broadcast,
        {
            "type": "DONATION_COMPLETED",
            "donation_id": str(donation_id),
            "volunteer_id": str(current_user.id),
        },
    )

    try:
        from app.interfaces.notifications_router import create_notification

        if donation.ngo_id:
            create_notification(
                db,
                donation.ngo_id,
                f"Donation #{str(donation_id)[:8]} completed by volunteer",
                "completion",
            )
        if donation.donor_id:
            create_notification(
                db,
                donation.donor_id,
                "Your donation has been delivered successfully!",
                "completion",
            )
    except Exception:
        pass

    try:
        from app.services import certificate_service

        if donation.donor_id:
            certificate_service.check_and_generate_certificate(
                donation.donor_id, "donor", db, background_tasks
            )
        if current_user.id:
            certificate_service.check_and_generate_certificate(
                current_user.id, "volunteer", db, background_tasks
            )
    except Exception as e:
        logger.warning(f"Certificate generation check failed: {e}")

    return {
        "success": True,
        "message": "Donation completed successfully!",
        "donation_id": str(donation_id),
    }


@router.get("/{donation_id}/lifecycle")
def get_donation_lifecycle(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Get full lifecycle tracking info for a donation.
    Returns timestamps, durations, and audit event history.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    # Compute lifecycle info
    lifecycle = donation_service.compute_lifecycle_info(donation)

    # Fetch audit events
    events = (
        db.query(models.DonationEvent)
        .filter(models.DonationEvent.donation_id == donation_id)
        .order_by(models.DonationEvent.timestamp.asc())
        .all()
    )
    event_list = [
        {
            "id": str(e.id),
            "action": e.action,
            "performed_by": str(e.performed_by) if e.performed_by else None,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in events
    ]

    return {
        "donation_id": str(donation_id),
        "lifecycle_status": lifecycle["lifecycle_status"],
        "timestamps": lifecycle["timestamps"],
        "durations": lifecycle["durations"],
        "events": event_list,
    }


@router.post("/{donation_id}/confirm-received")
def confirm_donation_received(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.NGO])),
):
    """
    NGO confirms receipt of a delivered donation.
    Only allowed when donation status is COMPLETED and received_at is NULL.
    Sets received_at and logs a RECEIVED event.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if donation.ngo_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Only the claiming NGO can confirm receipt"
        )

    if donation.status != models.DonationStatusEnum.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm receipt. Donation must be delivered first. Current status: {donation.status.value}",
        )

    # Idempotent: if already received, return success
    if donation.received_at is not None:
        return {
            "success": True,
            "message": "Donation already confirmed as received",
            "donation_id": str(donation_id),
            "received_at": donation.received_at.isoformat(),
        }

    now = datetime.now(timezone.utc)
    donation.received_at = now
    donation_service._log_donation_event(db, donation_id, "RECEIVED", current_user.id)
    db.commit()

    return {
        "success": True,
        "message": "Donation receipt confirmed successfully",
        "donation_id": str(donation_id),
        "received_at": now.isoformat(),
    }


@router.post("/{donation_id}/ngo-cancel")
def ngo_cancel_donation(
    donation_id: uuid.UUID,
    body: Optional[schemas.CancelDonationRequest] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.NGO])),
):
    """
    NGO cancels an assigned donation.
    Sets status to cancelled and unassigns volunteer safely.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if donation.ngo_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your donation")

    if donation.status in [
        models.DonationStatusEnum.COMPLETED,
        models.DonationStatusEnum.CANCELLED,
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel donation with status '{donation.status.value}'",
        )

    reason = body.cancel_reason if body and body.cancel_reason else "Cancelled by NGO"
    donation.status = models.DonationStatusEnum.CANCELLED
    donation.cancel_reason = reason

    if donation.delivery:
        if donation.delivery.volunteer:
            donation.delivery.volunteer.availability = "available"
        db.delete(donation.delivery)

    if donation.volunteer_id:
        volunteer = (
            db.query(models.User)
            .filter(models.User.id == donation.volunteer_id)
            .first()
        )
        if volunteer:
            volunteer.availability = "available"

    donation.volunteer_id = None
    donation.delivery_status = "cancelled"
    donation.otp_code = None
    donation.otp_verified = False
    donation.otp_generated_at = None
    donation.otp_last_sent_at = None

    db.commit()

    return {
        "success": True,
        "message": "Donation cancelled successfully",
        "donation_id": str(donation_id),
        "cancel_reason": reason,
    }


# ── Delivery Completion Workflow Endpoints ────────────────────────────────────────


@router.post("/{donation_id}/mark-delivered")
def mark_delivery_delivered(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Delivery Partner marks the donation as DELIVERED (arrived at beneficiary location).
    Sets delivered_at timestamp and status = DELIVERED.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if donation.volunteer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not assigned to this donation")

    if not donation.picked_up_at and not donation.donation_received:
        raise HTTPException(
            status_code=400,
            detail="Cannot mark as delivered. Food must be picked up first.",
        )

    if donation.delivered_at is not None:
        return {
            "success": True,
            "message": "Donation already marked as delivered",
            "donation_id": str(donation_id),
            "delivered_at": donation.delivered_at.isoformat(),
        }

    now = datetime.now(timezone.utc)
    donation.delivered_at = now
    donation.delivery_status = "delivered"

    db.commit()
    db.refresh(donation)

    logger.info("Donation %s marked as delivered by %s", donation_id, current_user.id)

    return {
        "success": True,
        "message": "Donation delivered to beneficiary location",
        "donation_id": str(donation_id),
        "delivered_at": now.isoformat(),
    }


@router.post("/{donation_id}/confirm-delivery-complete")
def confirm_delivery_complete(
    donation_id: uuid.UUID,
    body: schemas.DeliveryCompletionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.NGO])),
):
    """
    NGO confirms final delivery completion with receiver name.
    Sets received_at, receiver_name, and completes the lifecycle.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if donation.ngo_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the claiming NGO can confirm delivery completion",
        )

    if not donation.delivered_at:
        raise HTTPException(
            status_code=400,
            detail="Cannot complete delivery. Donation must be marked as delivered first.",
        )

    if donation.received_at is not None:
        return {
            "success": True,
            "message": "Delivery already confirmed as complete",
            "donation_id": str(donation_id),
            "received_at": donation.received_at.isoformat(),
            "receiver_name": donation.receiver_name,
        }

    now = datetime.now(timezone.utc)
    donation.received_at = now
    donation.status = models.DonationStatusEnum.COMPLETED
    donation.delivery_status = "completed"

    if body.receiver_name:
        donation.receiver_name = body.receiver_name

    if body.otp_verified:
        donation.otp_verified = True

    db.commit()
    db.refresh(donation)

    beneficiary_name = None
    if donation.beneficiary_id:
        beneficiary = (
            db.query(models.Beneficiary)
            .filter(models.Beneficiary.id == donation.beneficiary_id)
            .first()
        )
        if beneficiary:
            beneficiary_name = beneficiary.name

    logger.info(
        "Donation %s delivery completed by %s, receiver: %s",
        donation_id,
        current_user.id,
        body.receiver_name,
    )

    return {
        "success": True,
        "message": "Delivery completed successfully",
        "donation_id": str(donation_id),
        "received_at": now.isoformat(),
        "receiver_name": donation.receiver_name,
        "beneficiary_name": beneficiary_name,
    }


@router.post("/{donation_id}/pickup")
def mark_pickup(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.VOLUNTEER])),
):
    """
    Delivery Partner marks the donation as picked up from donor.
    Sets picked_up_at timestamp.
    """
    donation = (
        db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if donation.volunteer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not assigned to this donation")

    if donation.picked_up_at is not None:
        return {
            "success": True,
            "message": "Donation already picked up",
            "donation_id": str(donation_id),
            "picked_up_at": donation.picked_up_at.isoformat(),
        }

    now = datetime.now(timezone.utc)
    donation.picked_up_at = now
    donation.delivery_status = "out_for_delivery"

    if donation.status == models.DonationStatusEnum.ASSIGNED:
        donation.status = models.DonationStatusEnum.PICKED_UP

    db.commit()
    db.refresh(donation)

    logger.info("Donation %s picked up by %s", donation_id, current_user.id)

    return {
        "success": True,
        "message": "Donation picked up successfully",
        "donation_id": str(donation_id),
        "picked_up_at": now.isoformat(),
    }

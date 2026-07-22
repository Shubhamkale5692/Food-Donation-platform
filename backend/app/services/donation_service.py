from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from app.domain import models, schemas
from app.core.constants import (
    TRUST_SCORE_INCREMENT,
    TRUST_SCORE_DECREMENT,
    TRUST_SCORE_MAX,
    TRUST_SCORE_MIN,
    RECOMMENDATION_DISTANCE_KM,
    OTP_MIN,
    OTP_MAX,
    OTP_VALIDITY_MINUTES,
    OTP_RESEND_COOLDOWN_SECONDS,
)
from datetime import datetime, timezone, timedelta
import uuid
import logging
import secrets

_donation_log = logging.getLogger("foodbridge.donation")
_assign_log = logging.getLogger("foodbridge.assign")
OTP_VALIDITY_SECONDS = OTP_VALIDITY_MINUTES * 60


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ── Lifecycle Tracking Helpers ───────────────────────────────────────────────


def _log_donation_event(
    db: Session,
    donation_id: uuid.UUID,
    action: str,
    performed_by: Optional[uuid.UUID] = None,
) -> None:
    """Insert an audit record into donation_events."""
    try:
        event = models.DonationEvent(
            donation_id=donation_id,
            action=action,
            performed_by=performed_by,
            timestamp=_now_utc(),
        )
        db.add(event)
    except Exception as e:
        logging.getLogger("foodbridge.lifecycle").warning(
            "Failed to log donation event %s for %s: %s", action, donation_id, e
        )


def _format_duration(seconds: Optional[float]) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds is None or seconds < 0:
        return "In Progress"
    total_minutes = int(seconds / 60)
    if total_minutes < 60:
        return f"{total_minutes} mins"
    hours = total_minutes // 60
    mins = total_minutes % 60
    if mins == 0:
        return f"{hours} hrs"
    return f"{hours} hrs {mins} mins"


def _lifecycle_status_from_donation(donation: models.Donation) -> str:
    """Derive lifecycle status string from donation state."""
    if donation.received_at is not None:
        return "RECEIVED"
    status_val = _status_value(donation.status)
    mapping = {
        "pending": "CREATED",
        "accepted": "ACCEPTED",
        "ready_for_distribution": "TESTED",
        "assigned": "ASSIGNED",
        "claimed": "CLAIMED",
        "in_progress": "IN_PROGRESS",
        "out_for_delivery": "OUT_FOR_DELIVERY",
        "delivered": "DELIVERED",
        "completed": "COMPLETED",
        "cancelled": "CANCELLED",
    }
    return mapping.get(status_val, "CREATED")


def compute_lifecycle_info(donation: models.Donation) -> dict:
    """Compute lifecycle timestamps and durations for a donation."""
    posted = _as_utc(donation.donation_posted_at) or _as_utc(donation.created_at)
    accepted = _as_utc(donation.pickup_accepted_at) or _as_utc(donation.assignment_time)
    picked = _as_utc(donation.picked_up_at) or _as_utc(donation.pickup_time)
    delivered = _as_utc(donation.delivered_at) or _as_utc(donation.delivery_time)
    received = _as_utc(donation.received_at)

    timestamps = {
        "posted": posted.isoformat() if posted else None,
        "accepted": accepted.isoformat() if accepted else None,
        "picked_up": picked.isoformat() if picked else None,
        "delivered": delivered.isoformat() if delivered else None,
        "received": received.isoformat() if received else None,
    }

    # Compute durations only when both timestamps exist
    total_secs = None
    travel_secs = None
    if received and posted:
        total_secs = (received - posted).total_seconds()
    elif delivered and posted:
        total_secs = (delivered - posted).total_seconds()

    if delivered and picked:
        travel_secs = (delivered - picked).total_seconds()

    durations = {
        "total": _format_duration(total_secs),
        "travel": _format_duration(travel_secs),
    }

    return {
        "lifecycle_status": _lifecycle_status_from_donation(donation),
        "timestamps": timestamps,
        "durations": durations,
    }


def enrich_donation_lifecycle(donation: models.Donation) -> None:
    """Attach computed lifecycle fields to a donation object for API response."""
    info = compute_lifecycle_info(donation)
    setattr(donation, "lifecycle_status", info["lifecycle_status"])
    setattr(donation, "lifecycle_timestamps", info["timestamps"])
    setattr(donation, "lifecycle_durations", info["durations"])


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_role(role: Optional[str]) -> Optional[str]:
    value = str(role or "").strip().lower()
    if value == "donor":
        return "DONOR"
    if value == "ngo":
        return "NGO"
    if value == "volunteer":
        return "VOLUNTEER"
    if value == "admin":
        return "ADMIN"
    if value == "global_pending":
        return "GLOBAL_PENDING"
    return None


def _status_value(status_obj) -> str:
    if hasattr(status_obj, "value"):
        return str(status_obj.value).lower()
    return str(status_obj or "").lower()


def _is_otp_scope_active(donation: models.Donation) -> bool:
    return (
        _status_value(donation.status) == models.DonationStatusEnum.ASSIGNED.value
        and donation.volunteer_id is not None
        and not bool(donation.otp_verified)
    )


def get_otp_expiry_at(donation: models.Donation) -> Optional[datetime]:
    if not donation.otp_generated_at:
        return None
    generated_at = _as_utc(donation.otp_generated_at)
    if generated_at is None:
        return None
    return generated_at + timedelta(minutes=OTP_VALIDITY_MINUTES)


def get_otp_seconds_remaining(
    donation: models.Donation, now: Optional[datetime] = None
) -> Optional[int]:
    if not donation.otp_code or not donation.otp_generated_at:
        return None
    now = _as_utc(now) or _now_utc()
    expires_at = get_otp_expiry_at(donation)
    if not expires_at:
        return None
    return max(0, int((expires_at - now).total_seconds()))


def get_otp_resend_available_in_seconds(
    donation: models.Donation, now: Optional[datetime] = None
) -> int:
    if not donation.otp_last_sent_at:
        return 0
    now = _as_utc(now) or _now_utc()
    last_sent = _as_utc(donation.otp_last_sent_at)
    if not last_sent:
        return 0
    elapsed = int((now - last_sent).total_seconds())
    return max(0, OTP_RESEND_COOLDOWN_SECONDS - elapsed)


def _new_otp_code() -> str:
    return f"{secrets.randbelow(OTP_MAX - OTP_MIN + 1) + OTP_MIN:06d}"


def set_donation_otp(
    db: Session,
    donation: models.Donation,
    otp_code: str,
    generated_at: Optional[datetime] = None,
) -> None:
    generated_at = _as_utc(generated_at) or _now_utc()
    donation.otp_code = otp_code
    donation.otp_verified = False
    donation.otp_generated_at = generated_at
    donation.otp_last_sent_at = generated_at

    delivery = (
        db.query(models.Delivery)
        .filter(models.Delivery.donation_id == donation.id)
        .first()
    )
    if delivery:
        delivery.otp = otp_code


def clear_donation_otp(donation: models.Donation) -> None:
    donation.otp_code = None
    donation.otp_verified = False
    donation.otp_generated_at = None
    donation.otp_last_sent_at = None


def create_or_regenerate_pickup_otp(
    db: Session,
    donation: models.Donation,
    *,
    bypass_cooldown: bool = False,
) -> tuple[Optional[str], int]:
    now = _now_utc()
    cooldown_remaining = 0
    if not bypass_cooldown:
        cooldown_remaining = get_otp_resend_available_in_seconds(donation, now=now)
        if cooldown_remaining > 0:
            return None, cooldown_remaining

    otp_code = _new_otp_code()
    set_donation_otp(db, donation, otp_code=otp_code, generated_at=now)
    return otp_code, 0


def auto_rotate_expired_pickup_otp(
    db: Session,
    donation: models.Donation,
    *,
    now: Optional[datetime] = None,
) -> bool:
    now = _as_utc(now) or _now_utc()
    if not donation.otp_code or not _is_otp_scope_active(donation):
        return False
    remaining = get_otp_seconds_remaining(donation, now=now)
    if remaining is None or remaining > 0:
        return False
    set_donation_otp(db, donation, otp_code=_new_otp_code(), generated_at=now)
    return True


def get_donation_otp_metadata(
    donation: models.Donation, now: Optional[datetime] = None
) -> dict:
    now = _as_utc(now) or _now_utc()
    expires_at = get_otp_expiry_at(donation)
    seconds_remaining = get_otp_seconds_remaining(donation, now=now)

    return {
        "otp_generated_at": _as_utc(donation.otp_generated_at).isoformat()
        if donation.otp_generated_at
        else None,
        "otp_expires_at": expires_at.isoformat() if expires_at else None,
        "otp_seconds_remaining": seconds_remaining,
        "otp_validity_seconds": OTP_VALIDITY_SECONDS if donation.otp_code else None,
        "otp_resend_available_in_seconds": get_otp_resend_available_in_seconds(
            donation, now=now
        )
        if donation.otp_code
        else 0,
        "otp_regenerate_cooldown_seconds": OTP_RESEND_COOLDOWN_SECONDS,
    }


def apply_otp_view_for_donation(
    donation: models.Donation,
    *,
    viewer_role: Optional[str],
    viewer_user_id: Optional[uuid.UUID],
) -> None:
    metadata = get_donation_otp_metadata(donation)
    setattr(donation, "otp_expires_at", _as_utc(get_otp_expiry_at(donation)))
    setattr(donation, "otp_seconds_remaining", metadata["otp_seconds_remaining"])
    setattr(donation, "otp_validity_seconds", metadata["otp_validity_seconds"])
    setattr(
        donation,
        "otp_resend_available_in_seconds",
        metadata["otp_resend_available_in_seconds"],
    )
    setattr(
        donation,
        "otp_regenerate_cooldown_seconds",
        metadata["otp_regenerate_cooldown_seconds"],
    )

    show_otp_to_donor = (
        viewer_role == "DONOR"
        and viewer_user_id is not None
        and donation.donor_id == viewer_user_id
        and bool(donation.otp_code)
        and _is_otp_scope_active(donation)
    )

    if not show_otp_to_donor:
        donation.otp_code = None


def create_donation(
    db: Session, donation_in: schemas.DonationCreate, donor_id: uuid.UUID
) -> models.Donation:
    # Use pickup_latitude/longitude if latitude/longitude not provided
    lat = (
        donation_in.latitude
        if donation_in.latitude is not None
        else donation_in.pickup_latitude
    )
    lng = (
        donation_in.longitude
        if donation_in.longitude is not None
        else donation_in.pickup_longitude
    )

    now = _now_utc()
    db_donation = models.Donation(
        donor_id=donor_id,
        food_type=donation_in.food_type,
        quantity=donation_in.quantity,
        expiry_time=donation_in.expiry_time,
        latitude=lat,
        longitude=lng,
        pickup_latitude=donation_in.pickup_latitude,
        pickup_longitude=donation_in.pickup_longitude,
        pickup_address=donation_in.pickup_address,
        image_url=donation_in.image_url,
        status=models.DonationStatusEnum.PENDING,
        freshness_status=donation_in.freshness_status
        or models.FreshnessStatusEnum.UNKNOWN,
        ai_confidence_score=donation_in.ai_confidence_score,
        image_hash=donation_in.image_hash,
        image_source=donation_in.image_source,
        # Lifecycle: set posted timestamp
        donation_posted_at=now,
        # start_time is intentionally NOT set here.
        # It is set when a volunteer is assigned, so total_duration
        # accurately reflects actual delivery travel time.
    )
    db.add(db_donation)
    try:
        db.commit()
        db.refresh(db_donation)
    except Exception as e:
        db.rollback()
        _donation_log.error("Failed to create donation: %s", str(e))
        raise ValueError(f"Failed to create donation: {str(e)}")
    _log_donation_event(db, db_donation.id, "CREATED", donor_id)
    _donation_log.info(
        "Donation Created: %s by donor %s", donation_in.food_type, donor_id
    )
    return db_donation


def get_donations(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    ngo_id: Optional[uuid.UUID] = None,
    volunteer_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = None,
    donor_id: Optional[uuid.UUID] = None,
    role: Optional[str] = None,
) -> List[models.Donation]:
    from sqlalchemy import or_, and_

    query = db.query(models.Donation).options(joinedload(models.Donation.donor))

    from app.domain.models import DonationStatusEnum

    _donation_log.info(
        "get_donations called: role=%s, ngo_id=%s, donor_id=%s, volunteer_id=%s",
        role,
        ngo_id,
        donor_id,
        volunteer_id,
    )

    if role == "DONOR" or donor_id:
        # DONOR view: only their own donations
        query = query.filter(models.Donation.donor_id == donor_id)

    elif role == "NGO" or role == "GLOBAL_PENDING" or ngo_id:
        if role == "GLOBAL_PENDING":
            # For pending donations, use string comparison for flexibility
            query = query.filter(
                or_(
                    models.Donation.status == "pending",
                    models.Donation.status == DonationStatusEnum.PENDING,
                )
            )
        else:
            # For NGO: show pending globally OR their claimed donations
            # Exclude completed and cancelled donations by default
            query = query.filter(
                or_(
                    models.Donation.status == "pending",
                    models.Donation.status == DonationStatusEnum.PENDING,
                    models.Donation.ngo_id == ngo_id,
                ),
                ~models.Donation.status.in_(
                    [
                        "cancelled",
                        "completed",
                        DonationStatusEnum.CANCELLED,
                        DonationStatusEnum.COMPLETED,
                    ]
                ),
            )

    elif role == "VOLUNTEER" or volunteer_id:
        # VOLUNTEER view: return assigned deliveries ONLY (via Delivery table)
        from app.domain.models import Delivery

        query = query.join(Delivery, Delivery.donation_id == models.Donation.id).filter(
            Delivery.volunteer_id == volunteer_id
        )

    if status_filter:
        # Allow both string and enum for status filter, handling case variants
        status_str = getattr(status_filter, "value", str(status_filter))
        query = query.filter(
            or_(
                models.Donation.status == status_str,
                models.Donation.status == status_str.lower(),
                models.Donation.status == status_str.upper(),
                models.Donation.status == status_str.capitalize(),
            )
        )

    donations = query.offset(skip).limit(limit).all()
    _donation_log.debug("DONATIONS FOUND=%d", len(donations))

    otp_rotated = False
    now = _now_utc()
    for donation in donations:
        if auto_rotate_expired_pickup_otp(db, donation, now=now):
            otp_rotated = True

    if otp_rotated:
        db.commit()
        for donation in donations:
            db.refresh(donation)

    # AI Module 2: Smart NGO Recommendation
    # If the request comes from a specific NGO, flag nearby donations (<5km)
    if ngo_id:
        ngo_user = db.query(models.User).filter(models.User.id == ngo_id).first()
        if (
            ngo_user
            and ngo_user.profile
            and ngo_user.profile.latitude
            and ngo_user.profile.longitude
        ):
            for donation in donations:
                dist = calculate_distance(
                    donation.latitude or 0.0,
                    donation.longitude or 0.0,
                    ngo_user.profile.latitude,
                    ngo_user.profile.longitude,
                )
                if (
                    dist <= RECOMMENDATION_DISTANCE_KM
                    and donation.status == DonationStatusEnum.PENDING
                ):
                    # Monkey-patch an is_recommended attribute for Pydantic schema
                    setattr(donation, "is_recommended", True)
                else:
                    setattr(donation, "is_recommended", False)

    # Enrich donations with NGO and volunteer names for donor dashboard
    normalized_role = _normalize_role(role)
    viewer_user_id = (
        donor_id
        if normalized_role == "DONOR"
        else ngo_id
        if normalized_role == "NGO"
        else volunteer_id
        if normalized_role == "VOLUNTEER"
        else None
    )

    for donation in donations:
        # BUG-6 Fix: ensure is_recommended is always set so Pydantic doesn't AttributeError
        if not hasattr(donation, "is_recommended"):
            setattr(donation, "is_recommended", False)
        enrich_donation_with_names(db, donation)
        enrich_donation_lifecycle(donation)
        apply_otp_view_for_donation(
            donation,
            viewer_role=normalized_role,
            viewer_user_id=viewer_user_id,
        )

    return donations if donations else []


def enrich_donation_with_names(db: Session, donation):
    """Add NGO name and volunteer name to donation for response"""
    if donation.ngo_id:
        ngo = db.query(models.User).filter(models.User.id == donation.ngo_id).first()
        if ngo and ngo.profile:
            donation.ngo_name = ngo.profile.name
        elif ngo:
            donation.ngo_name = ngo.email.split("@")[0]

    if donation.volunteer_id:
        vol = (
            db.query(models.User)
            .filter(models.User.id == donation.volunteer_id)
            .first()
        )
        if vol and vol.profile:
            donation.volunteer_name = vol.profile.name
            donation.volunteer_phone = vol.profile.phone or ""
        elif vol:
            donation.volunteer_name = vol.email.split("@")[0]
            donation.volunteer_phone = ""

    return donation


def get_active_donations(
    db: Session, skip: int = 0, limit: int = 100
) -> List[models.Donation]:
    """
    Get active donations: Pending, Accepted, Assigned, In-Transit, Picked-Up.
    BUG-11 Fix: PICKED_UP was missing — donations picked up are still active.
    """
    active_statuses = [
        models.DonationStatusEnum.PENDING,
        models.DonationStatusEnum.ACCEPTED,
        models.DonationStatusEnum.ASSIGNED,
        models.DonationStatusEnum.IN_PROGRESS,
        models.DonationStatusEnum.PICKED_UP,  # BUG-11 Fix
    ]
    query = db.query(models.Donation).options(joinedload(models.Donation.donor))
    query = query.filter(models.Donation.status.in_(active_statuses))
    return query.offset(skip).limit(limit).all()


import math


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees).
    Safe against None values.
    """
    if any(v is None for v in [lat1, lon1, lat2, lon2]):
        return 0.0

    from math import radians, cos, sin, asin, sqrt

    R = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    a = max(0.0, min(a, 1.0))
    c = 2 * asin(sqrt(a))
    return R * c


def get_donation_by_id(
    db: Session, donation_id: uuid.UUID
) -> Optional[models.Donation]:
    return db.query(models.Donation).filter(models.Donation.id == donation_id).first()


def update_donation_status(
    db: Session,
    donation_id: uuid.UUID,
    status: models.DonationStatusEnum,
    actor_id: Optional[uuid.UUID] = None,
    actor_role: Optional[models.RoleEnum] = None,
) -> Optional[models.Donation]:
    db_donation = get_donation_by_id(db, donation_id)
    if not db_donation:
        return None

    try:
        # Role-based status transition guardrails
        if actor_role == models.RoleEnum.NGO:
            if status not in [
                models.DonationStatusEnum.ACCEPTED,
                models.DonationStatusEnum.CANCELLED,
            ]:
                raise HTTPException(
                    status_code=403,
                    detail="NGO can only set status to accepted or cancelled",
                )
            if status == models.DonationStatusEnum.ACCEPTED:
                if db_donation.status != models.DonationStatusEnum.PENDING:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Only pending donations can be accepted. Current status: {db_donation.status.value}",
                    )
            if status == models.DonationStatusEnum.CANCELLED:
                if db_donation.ngo_id and actor_id and db_donation.ngo_id != actor_id:
                    raise HTTPException(
                        status_code=403,
                        detail="You can only cancel donations claimed by your NGO",
                    )

        elif actor_role == models.RoleEnum.VOLUNTEER:
            if status != models.DonationStatusEnum.COMPLETED:
                raise HTTPException(
                    status_code=403,
                    detail="Volunteer can only mark donation as completed",
                )
            if actor_id and db_donation.volunteer_id != actor_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not assigned to this donation",
                )

        db_donation.status = status
        if status == models.DonationStatusEnum.ACCEPTED and actor_id:
            db_donation.ngo_id = actor_id

        if status == models.DonationStatusEnum.COMPLETED:
            now_completed = _now_utc()
            db_donation.delivery_status = "delivered"
            db_donation.delivery_time = now_completed
            # Lifecycle: set delivered_at
            db_donation.delivered_at = now_completed
            # Use start_time (set at assignment) or fallback to assignment_time.
            start_ref = db_donation.start_time or db_donation.assignment_time
            if start_ref:
                start_dt = start_ref
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                db_donation.total_duration = int(
                    (db_donation.delivery_time - start_dt).total_seconds() / 60
                )
            _log_donation_event(db, db_donation.id, "DELIVERED", actor_id)

            clear_donation_otp(db_donation)
            if db_donation.delivery:
                db_donation.delivery.status = models.DeliveryStatusEnum.DELIVERED
                db_donation.delivery.completed_at = datetime.now(timezone.utc)
                db_donation.delivery.otp = None
            # AI Module 3: Reward system - Add trust score to donor (capped at 100) and completed_deliveries to volunteer
            if db_donation.donor:
                db_donation.donor.trust_score = min(
                    TRUST_SCORE_MAX,
                    db_donation.donor.trust_score + TRUST_SCORE_INCREMENT,
                )
            if db_donation.volunteer_id:
                volunteer = (
                    db.query(models.User)
                    .filter(models.User.id == db_donation.volunteer_id)
                    .first()
                )
                if volunteer and volunteer.completed_deliveries is not None:
                    volunteer.completed_deliveries += 1
                elif volunteer:
                    volunteer.completed_deliveries = 1
                if volunteer:
                    volunteer.availability = "available"
        db.commit()
        db.refresh(db_donation)
    except Exception as e:
        db.rollback()
        raise e
    return db_donation


def cancel_donation(
    db: Session,
    donation_id: uuid.UUID,
    donor_id: uuid.UUID,
    cancel_reason: str = None,
) -> Optional[models.Donation]:
    """
    Donor cancels their own donation.
    - Sets status → CANCELLED and stores the reason.
    - Deletes linked Delivery record so the volunteer is freed.
    - Deducts trust score (fraud deterrent).
    """
    db_donation = get_donation_by_id(db, donation_id)
    if not db_donation or db_donation.donor_id != donor_id:
        return None
    # Cannot cancel already-completed or in-progress deliveries
    if db_donation.status in [
        models.DonationStatusEnum.COMPLETED,
        models.DonationStatusEnum.IN_PROGRESS,
        models.DonationStatusEnum.PICKED_UP,
    ]:
        return None

    db_donation.status = models.DonationStatusEnum.CANCELLED
    db_donation.cancel_reason = cancel_reason

    # Free the volunteer: delete the Delivery record so volunteer is unblocked
    if db_donation.delivery:
        # FIX 1.1: Reset volunteer availability back to 'available'
        if db_donation.delivery.volunteer:
            db_donation.delivery.volunteer.availability = "available"
        db_donation.delivery.otp = None
        db.delete(db_donation.delivery)

    # Reset all assignment fields on the donation row
    db_donation.volunteer_id = None
    db_donation.ngo_id = None  # Also clear the NGO that claimed this donation
    db_donation.delivery_status = "cancelled"
    clear_donation_otp(db_donation)

    # AI Module 4: Fraud Detection – deduct trust score for cancellation
    if db_donation.donor:
        db_donation.donor.trust_score = max(
            TRUST_SCORE_MIN, db_donation.donor.trust_score - TRUST_SCORE_DECREMENT
        )

    db.commit()
    db.refresh(db_donation)
    return db_donation


_svc_log = logging.getLogger("foodbridge.donation_service")


def claim_donation(
    db: Session, donation_id: uuid.UUID, ngo_id: uuid.UUID
) -> Optional[models.Donation]:
    """
    NGO accepts/claims a pending donation → status=Accepted.
    Records ngo_id for the accepting NGO.
    Only accepts donations with status=PENDING.
    """
    try:
        donation = get_donation_by_id(db, donation_id)
        if not donation:
            _svc_log.warning("claim_donation: donation %s not found", donation_id)
            return None
        if donation.status != models.DonationStatusEnum.PENDING:
            _svc_log.warning(
                "claim_donation: donation %s has status=%s — only PENDING donations can be accepted",
                donation_id,
                donation.status,
            )
            return None

        donation.status = models.DonationStatusEnum.ACCEPTED
        donation.ngo_id = ngo_id
        # Lifecycle: set accepted timestamp
        donation.pickup_accepted_at = _now_utc()
        if donation.pickup_address:
            donation.pickup_location = donation.pickup_address

        # Try to create delivery record - if it fails, still accept the donation
        try:
            # Check if delivery already exists for this donation
            existing_delivery = (
                db.query(models.Delivery)
                .filter(models.Delivery.donation_id == donation.id)
                .first()
            )

            if not existing_delivery:
                delivery = models.Delivery(
                    donation_id=donation.id,
                    ngo_id=ngo_id,
                    volunteer_id=None,
                    status=models.DeliveryStatusEnum.PENDING,
                )
                db.add(delivery)
        except Exception as delivery_err:
            _svc_log.warning(
                "claim_donation: could not create delivery record: %s",
                str(delivery_err),
            )
            # Continue without failing - the donation can still be accepted

        _log_donation_event(db, donation.id, "ACCEPTED", ngo_id)
        db.commit()
        db.refresh(donation)
        # BUG-10 Fix: refresh delivery record so caller gets the DB-generated UUID
        try:
            existing_delivery_refreshed = (
                db.query(models.Delivery)
                .filter(models.Delivery.donation_id == donation.id)
                .first()
            )
            if existing_delivery_refreshed:
                db.refresh(existing_delivery_refreshed)
        except Exception:
            pass
        _donation_log.info("NGO %s accepted donation %s", ngo_id, donation_id)
        return donation
    except Exception as e:
        _svc_log.exception(
            "claim_donation: unexpected error for donation %s: %s", donation_id, str(e)
        )
        db.rollback()
        raise


# NOTE: _assign_log is already defined at module level — no redefinition needed.


def get_active_delivery_count(db: Session, volunteer_id: uuid.UUID) -> int:
    return (
        db.query(models.Delivery)
        .join(models.Donation, models.Delivery.donation_id == models.Donation.id)
        .filter(
            models.Delivery.volunteer_id == volunteer_id,
            models.Donation.status.in_(
                [
                    models.DonationStatusEnum.ASSIGNED,
                    models.DonationStatusEnum.IN_PROGRESS,
                ]
            ),
        )
        .count()
    )


def assign_volunteer(
    db: Session,
    donation_id: uuid.UUID,
    ngo_id: uuid.UUID,
    volunteer_id: uuid.UUID,
) -> Optional[models.Delivery]:
    """
    Assign a volunteer to a donation (MANUAL ASSIGNMENT ONLY).
    Uses database row-level locking via with_for_update().
    """
    from fastapi import HTTPException

    _assign_log.info(
        "[assign_volunteer] START  donation=%s  ngo=%s  requested_vol=%s",
        donation_id,
        ngo_id,
        volunteer_id,
    )
    _assign_log.info(
        "ASSIGN → donation=%s, volunteer=%s, ngo=%s",
        donation_id,
        volunteer_id,
        ngo_id,
    )

    if not volunteer_id:
        _assign_log.warning(
            "[assign_volunteer] Manual assignment requires a volunteer_id"
        )
        return None

    # Use with_for_update to defensively lock the donation row against
    # parallel assignment attempts.
    donation = (
        db.query(models.Donation)
        .filter(models.Donation.id == donation_id)
        .with_for_update()
        .first()
    )
    if not donation:
        _assign_log.warning("[assign_volunteer] Donation %s not found", donation_id)
        return None

    if donation.status not in (
        models.DonationStatusEnum.ACCEPTED,
        models.DonationStatusEnum.READY_FOR_DISTRIBUTION,
    ):
        _assign_log.warning(
            "[assign_volunteer] Donation %s has status=%s — cannot assign",
            donation_id,
            donation.status,
        )
        return None

    existing_delivery = (
        db.query(models.Delivery)
        .filter(models.Delivery.donation_id == donation_id)
        .first()
    )

    if existing_delivery:
        _assign_log.info(
            "[assign_volunteer] Found existing delivery %s, updating it.",
            existing_delivery.id,
        )
        existing_delivery.volunteer_id = volunteer_id
        existing_delivery.status = models.DeliveryStatusEnum.ASSIGNED
        existing_delivery.otp = None
        delivery = existing_delivery
    else:
        _assign_log.info("[assign_volunteer] Creating new delivery record.")
        delivery = models.Delivery(
            donation_id=donation_id,
            ngo_id=ngo_id,
            volunteer_id=volunteer_id,
            otp=None,
            status=models.DeliveryStatusEnum.ASSIGNED,
        )
        db.add(delivery)

    best_volunteer = (
        db.query(models.User)
        .filter(models.User.id == volunteer_id)
        .with_for_update()
        .first()
    )
    if not best_volunteer:
        _assign_log.warning(
            "[assign_volunteer] Requested volunteer %s not found",
            volunteer_id,
        )
        return None

    _assign_log.info(
        "[assign_volunteer] Chosen volunteer: %s (%s)",
        best_volunteer.id,
        best_volunteer.email,
    )

    donation.status = models.DonationStatusEnum.ASSIGNED
    donation.volunteer_id = best_volunteer.id
    donation.delivery_status = "assigned"

    # Import clear_donation_otp explicitly if not locally scoped
    clear_donation_otp(donation)

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    donation.assignment_time = now
    # start_time marks when the delivery clock begins (volunteer assigned).
    # total_duration = delivery_time - start_time = actual travel time in mins.
    donation.start_time = now

    try:
        db.flush()
        best_volunteer.availability = "busy"
        db.commit()
        db.refresh(donation)
        db.refresh(best_volunteer)
        db.refresh(delivery)

        _assign_log.info(
            "[assign_volunteer] SUCCESS delivery=%s | donation.status=%s | donation.volunteer_id=%s | volunteer.availability=%s",
            delivery.id,
            donation.status,
            donation.volunteer_id,
            best_volunteer.availability,
        )
        _assign_log.info(
            "Volunteer %s assigned to donation %s", best_volunteer.id, donation.id
        )
        _assign_log.info(
            "ASSIGN SUCCESS → Delivery(%s) created. Donation(%s) updated.",
            delivery.id,
            donation.id,
        )
        return delivery
    except Exception as exc:
        db.rollback()
        _assign_log.exception("[assign_volunteer] DB COMMIT ERROR: %s", exc)
        raise HTTPException(
            status_code=500, detail="Database assignment error: " + str(exc)
        )


def verify_delivery_otp(
    db: Session, donation_id: uuid.UUID, otp: str, volunteer_id: uuid.UUID
) -> Optional[models.Delivery]:
    try:
        otp = str(otp).strip()
        delivery = (
            db.query(models.Delivery)
            .filter(
                models.Delivery.donation_id == donation_id,
                models.Delivery.volunteer_id == volunteer_id,
            )
            .first()
        )
        # BUG-3 Fix: allow ASSIGNED or IN_PROGRESS delivery status for OTP verification
        if not delivery or delivery.status not in (
            models.DeliveryStatusEnum.ASSIGNED,
            models.DeliveryStatusEnum.IN_PROGRESS,
        ):
            return None

        if delivery.otp == otp:
            delivery.status = models.DeliveryStatusEnum.PICKED_UP
            now = _now_utc()

            if delivery.donation:
                delivery.donation.status = models.DonationStatusEnum.PICKED_UP
                delivery.donation.delivery_status = "picked_up"
                delivery.donation.otp_verified = True
                delivery.donation.pickup_time = now
                # Lifecycle: set picked_up_at
                delivery.donation.picked_up_at = now
                delivery.donation.otp_code = None
                delivery.donation.otp_generated_at = None
                delivery.donation.otp_last_sent_at = None
                # Note: volunteer_reached_donor and donation_received remain False
                # Volunteer must click buttons to update these
                _log_donation_event(db, delivery.donation.id, "PICKED_UP", volunteer_id)
            delivery.otp = None

            db.commit()
            db.refresh(delivery)
            return delivery
        return None
    except Exception as e:
        db.rollback()
        _assign_log.error(f"OTP verification error: {e}")
        return None


def reject_volunteer(db: Session, vol_id: str) -> Optional[models.User]:
    """
    Rejects a volunteer by setting their status to 'rejected'.
    """
    try:
        vol_uuid = uuid.UUID(vol_id)
    except ValueError:
        return None

    volunteer = db.query(models.User).filter(models.User.id == vol_uuid).first()
    if not volunteer:
        return None

    if volunteer.role != models.RoleEnum.VOLUNTEER:
        return None

    volunteer.volunteer_status = "rejected"
    volunteer.status = "rejected"
    db.commit()
    db.refresh(volunteer)
    return volunteer


def update_volunteer_location(
    db: Session, volunteer_id: uuid.UUID, lat: float, lng: float
) -> Optional[models.Profile]:
    profile = (
        db.query(models.Profile).filter(models.Profile.user_id == volunteer_id).first()
    )
    if profile:
        profile.current_lat = lat
        profile.current_lng = lng
        db.commit()
        db.refresh(profile)
    return profile

"""
NGO Router – FoodBridge
Provides NGO-specific stats, volunteer management, profile, and analytics endpoints.
All existing routes remain untouched.
"""

import logging
import uuid  # BUG-4/BUG-5 Fix: needed for UUID parsing in approve/reject volunteer
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract, or_
from app.domain import models, schemas
from app.infrastructure.database import get_db
from app.interfaces.deps import get_current_active_user, RoleChecker
from app.services.donation_service import (
    get_active_delivery_count,
    calculate_distance,
    assign_volunteer as donation_service_assign,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  GET /ngo/stats  – Overview dashboard stat cards
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/stats")
def get_ngo_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Returns dashboard stat-card values for the logged-in NGO:
    - active_donations  : Pending donations (available to claim)
    - active_volunteers : Approved+active volunteers for this NGO
    - items_distributed : Count of Completed donations
    - food_waste_diverted: Total quantity (units) of Completed donations
    """
    logger.info(
        f"get_ngo_stats called by user {current_user.id} with role {current_user.role}"
    )
    try:
        if current_user.role != models.RoleEnum.NGO:
            return {
                "active_donations": 0,
                "accepted_donations": 0,
                "active_volunteers": 0,
                "items_distributed": 0,
                "food_waste_diverted": 0,
                "total_donations": 0,
                "total_volunteers": 0,
            }

        ngo_id = current_user.id
        # BUG-15 Fix: ngo_lat and ngo_lng were fetched but never used in this function.
        # Removed to avoid dead variables.

        # Active donations (Pending – any NGO can see these)
        active_donations = (
            db.query(models.Donation)
            .filter(models.Donation.status == models.DonationStatusEnum.PENDING)
            .count()
        )

        # Also count Accepted donations claimed by this NGO
        accepted_by_ngo = (
            db.query(models.Donation)
            .filter(
                models.Donation.ngo_id == ngo_id,
                models.Donation.status == models.DonationStatusEnum.ACCEPTED,
            )
            .count()
        )

        # Active volunteers for this NGO
        active_volunteers = (
            db.query(models.User)
            .filter(
                models.User.ngo_id == ngo_id,
                models.User.role == models.RoleEnum.VOLUNTEER,
                models.User.volunteer_status == "approved",
                models.User.is_active == True,
            )
            .count()
        )

        # Items distributed = completed donations this NGO accepted
        items_distributed = (
            db.query(models.Donation)
            .filter(
                models.Donation.ngo_id == ngo_id,
                models.Donation.status == models.DonationStatusEnum.COMPLETED,
            )
            .count()
        )

        # Food waste diverted = total quantity of completed donations for this NGO
        food_waste_diverted = (
            db.query(func.sum(models.Donation.quantity))
            .filter(
                models.Donation.ngo_id == ngo_id,
                models.Donation.status == models.DonationStatusEnum.COMPLETED,
            )
            .scalar()
            or 0
        )

        # Total donations handled by NGO (all statuses)
        total_donations = (
            db.query(models.Donation).filter(models.Donation.ngo_id == ngo_id).count()
        )

        # Total volunteers (all statuses)
        total_volunteers = (
            db.query(models.User)
            .filter(
                models.User.ngo_id == ngo_id,
                models.User.role == models.RoleEnum.VOLUNTEER,
            )
            .count()
        )

        return {
            "active_donations": active_donations,  # Truly pending for "Incoming"
            "accepted_donations": accepted_by_ngo,  # "Accepted" but not yet Picked Up
            "active_volunteers": active_volunteers,
            "items_distributed": items_distributed,
            "food_waste_diverted": food_waste_diverted,
            "total_donations": total_donations,
            "total_volunteers": total_volunteers,
        }
    except Exception as e:
        logger.exception("Error in get_ngo_stats: %s", str(e))
        return {
            "active_donations": 0,
            "accepted_donations": 0,
            "active_volunteers": 0,
            "items_distributed": 0,
            "food_waste_diverted": 0,
            "total_donations": 0,
            "total_volunteers": 0,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  GET /ngo/volunteers  – All volunteers for this NGO (with delivery stats)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/volunteers")
def get_ngo_volunteers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Returns all volunteers (any status) for the current NGO with delivery stats.
    """
    if current_user.role != models.RoleEnum.NGO:
        return []

    ngo_id = current_user.id

    volunteers = (
        db.query(models.User)
        .filter(
            models.User.ngo_id == ngo_id,
            models.User.role == models.RoleEnum.VOLUNTEER,
        )
        .all()
    )

    result = []
    for v in volunteers:
        profile = v.profile

        # Count assigned deliveries (Accepted / In-Transit)
        assigned = (
            db.query(models.Delivery)
            .join(models.Donation, models.Delivery.donation_id == models.Donation.id)
            .filter(
                models.Delivery.volunteer_id == v.id,
                models.Donation.status.in_(
                    [
                        models.DonationStatusEnum.ACCEPTED,
                        models.DonationStatusEnum.IN_PROGRESS,
                    ]
                ),
            )
            .count()
        )

        # Count completed deliveries
        completed = (
            db.query(models.Delivery)
            .join(models.Donation, models.Delivery.donation_id == models.Donation.id)
            .filter(
                models.Delivery.volunteer_id == v.id,
                models.Donation.status == models.DonationStatusEnum.COMPLETED,
            )
            .count()
        )

        result.append(
            {
                "id": str(v.id),
                "name": profile.name if profile else v.email.split("@")[0],
                "email": v.email,
                "phone": profile.phone if profile else "",
                "location": profile.address if profile else "",
                "volunteer_status": v.volunteer_status or "pending",
                "is_active": v.is_active,
                "assigned_deliveries": assigned,
                "completed_deliveries": completed,
                "rating": round(v.rating or 5.0, 1),
                "joined": v.created_at.strftime("%b %d, %Y") if v.created_at else "",
            }
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  GET /ngo/available-volunteers  – Only approved, available volunteers
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/available-volunteers")
def get_available_volunteers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Returns only APPROVED volunteers for this NGO that can be assigned to deliveries.
    Used by the manual assign dropdown.
    Condition: volunteer_status = 'approved' AND ngo_id = current NGO
    """
    if current_user.role != models.RoleEnum.NGO:
        return []

    ngo_id = current_user.id
    ngo_lat = current_user.profile.latitude if current_user.profile else None
    ngo_lng = current_user.profile.longitude if current_user.profile else None

    from sqlalchemy import or_

    volunteers = (
        db.query(models.User)
        .filter(
            models.User.ngo_id == ngo_id,
            models.User.role == models.RoleEnum.VOLUNTEER,
            models.User.volunteer_status.ilike("approved"),
            or_(
                models.User.availability == "available",
                models.User.availability.is_(None),
            ),
        )
        .all()
    )

    result = []
    for v in volunteers:
        profile = v.profile
        active_deliveries = get_active_delivery_count(db, v.id)
        vol_lat = (
            v.location_lat
            if v.location_lat is not None
            else (profile.latitude if profile else None)
        )
        vol_lng = (
            v.location_lng
            if v.location_lng is not None
            else (profile.longitude if profile else None)
        )
        distance = None
        if (
            ngo_lat is not None
            and ngo_lng is not None
            and vol_lat is not None
            and vol_lng is not None
        ):
            distance = round(calculate_distance(ngo_lat, ngo_lng, vol_lat, vol_lng), 2)
        result.append(
            {
                "id": str(v.id),
                "name": profile.name if profile else v.email.split("@")[0],
                "email": v.email,
                "volunteer_status": "approved",
                "status": v.status or "approved",
                "availability": v.availability
                or ("available" if active_deliveries == 0 else "busy"),
                "active_deliveries": active_deliveries,
                "is_available": active_deliveries == 0,
                "location": profile.address if profile else "",
                "location_lat": vol_lat,
                "location_lng": vol_lng,
                "rating": round(v.rating or 5.0, 1),
                "completed_deliveries": v.completed_deliveries or 0,
                "distance": distance,
            }
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  GET /ngo/profile  – NGO profile
#  PUT /ngo/profile  – Update NGO profile
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/profile")
def get_ngo_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    if current_user.role != models.RoleEnum.NGO:
        return {}

    db_user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    profile = (
        db.query(models.Profile)
        .filter(models.Profile.user_id == current_user.id)
        .first()
    )
    return {
        "id": str(db_user.id),
        "email": db_user.email,
        "name": profile.name if profile else db_user.email.split("@")[0],
        "phone": profile.phone if profile else "",
        "address": profile.address if profile else "",
        "latitude": profile.latitude if profile else None,
        "longitude": profile.longitude if profile else None,
        "is_verified": db_user.is_verified,
        "created_at": db_user.created_at.strftime("%b %d, %Y")
        if db_user.created_at
        else "",
    }


@router.put("/profile")
def update_ngo_profile(
    body: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.NGO])),
):
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
    if "latitude" in body:
        lat = body["latitude"]
        try:
            profile.latitude = float(lat) if lat not in (None, "") else None
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Invalid latitude value")
    if "longitude" in body:
        lng = body["longitude"]
        try:
            profile.longitude = float(lng) if lng not in (None, "") else None
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Invalid longitude value")

    db.commit()
    db.refresh(profile)
    return {
        "success": True,
        "message": "Profile updated successfully",
        "name": profile.name,
        "phone": profile.phone,
        "address": profile.address,
        "latitude": profile.latitude,
        "longitude": profile.longitude,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  GET /ngo/analytics  – Monthly data for charts
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/analytics")
def get_ngo_analytics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Returns monthly donations counts and quantities for the last 6 months.
    Used to power Chart.js charts in the Reports section.
    """
    if current_user.role != models.RoleEnum.NGO:
        return {"monthly": [], "volunteer_performance": []}

    ngo_id = current_user.id
    current_year = datetime.now(timezone.utc).year

    monthly_data = []
    month_names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]

    for month in range(1, 13):
        count = (
            db.query(models.Donation)
            .filter(
                models.Donation.ngo_id == ngo_id,
                extract("year", models.Donation.created_at) == current_year,
                extract("month", models.Donation.created_at) == month,
            )
            .count()
        )
        qty = (
            db.query(func.sum(models.Donation.quantity))
            .filter(
                models.Donation.ngo_id == ngo_id,
                extract("year", models.Donation.created_at) == current_year,
                extract("month", models.Donation.created_at) == month,
                models.Donation.status == models.DonationStatusEnum.COMPLETED,
            )
            .scalar()
            or 0
        )
        monthly_data.append(
            {
                "month": month_names[month - 1],
                "donations": count,
                "meals": qty,
                "people_helped": max(0, qty // 3),  # estimate: 3 units feeds 1 person
            }
        )

    # Volunteer performance: top 5 by completed deliveries
    volunteers = (
        db.query(models.User)
        .filter(
            models.User.ngo_id == ngo_id,
            models.User.role == models.RoleEnum.VOLUNTEER,
            models.User.volunteer_status == "approved",
        )
        .all()
    )

    vol_perf = []
    for v in volunteers:
        profile = v.profile
        completed = (
            db.query(models.Delivery)
            .join(models.Donation, models.Delivery.donation_id == models.Donation.id)
            .filter(
                models.Delivery.volunteer_id == v.id,
                models.Donation.status == models.DonationStatusEnum.COMPLETED,
            )
            .count()
        )
        vol_perf.append(
            {
                "name": profile.name if profile else v.email.split("@")[0],
                "completed": completed,
            }
        )

    vol_perf.sort(key=lambda x: x["completed"], reverse=True)

    return {
        "monthly": monthly_data,
        "volunteer_performance": vol_perf[:5],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  GET /ngo/inventory  – Food inventory (accepted/in-transit donations)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/inventory")
def get_ngo_inventory(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Returns accepted/in-transit donations as inventory items for this NGO.
    """
    if current_user.role != models.RoleEnum.NGO:
        return []

    ngo_id = current_user.id
    result = []

    try:
        # Query donations without complex join to avoid errors
        from sqlalchemy import or_

        donations = (
            db.query(models.Donation)
            .filter(
                models.Donation.ngo_id == ngo_id,
                or_(
                    models.Donation.status == models.DonationStatusEnum.ACCEPTED,
                    models.Donation.status == models.DonationStatusEnum.ASSIGNED,
                    models.Donation.status == models.DonationStatusEnum.IN_PROGRESS,
                    models.Donation.status == models.DonationStatusEnum.PICKED_UP,
                    models.Donation.status == models.DonationStatusEnum.COMPLETED,
                ),
            )
            .order_by(models.Donation.created_at.desc())
            .all()
        )

        now = datetime.now(timezone.utc)
        for d in donations:
            try:
                # Calculate expiry label
                expiry_label = "Fresh"
                if d.expiry_time:
                    try:
                        delta = (d.expiry_time - now).total_seconds() / 3600
                        if delta < 0:
                            expiry_label = "Expired"
                        elif delta < 24:
                            expiry_label = "Risky"
                    except Exception:
                        pass

                # Override with AI freshness if available
                try:
                    if d.freshness_status:
                        freshness_val = (
                            d.freshness_status.value
                            if hasattr(d.freshness_status, "value")
                            else str(d.freshness_status)
                        )
                        if freshness_val and freshness_val != "unknown":
                            expiry_label = freshness_val
                except Exception:
                    pass

                # Get current status
                try:
                    current_status = (
                        d.status.value if hasattr(d.status, "value") else str(d.status)
                    )
                except Exception:
                    current_status = "unknown"

                # Try to get delivery info separately
                assigned_volunteer = None
                try:
                    delivery = (
                        db.query(models.Delivery)
                        .filter(models.Delivery.donation_id == d.id)
                        .first()
                    )
                    if delivery:
                        try:
                            current_status = (
                                delivery.status.value
                                if hasattr(delivery.status, "value")
                                else str(delivery.status)
                            )
                        except Exception:
                            pass

                        if delivery.volunteer_id:
                            try:
                                volunteer = (
                                    db.query(models.User)
                                    .filter(models.User.id == delivery.volunteer_id)
                                    .first()
                                )
                                if volunteer:
                                    if volunteer.profile and volunteer.profile.name:
                                        assigned_volunteer = volunteer.profile.name
                                    elif volunteer.email:
                                        assigned_volunteer = volunteer.email.split("@")[
                                            0
                                        ]
                            except Exception:
                                pass
                except Exception:
                    pass

                # Format times safely
                try:
                    expiry_time_str = (
                        d.expiry_time.strftime("%b %d, %Y %H:%M")
                        if d.expiry_time
                        else "N/A"
                    )
                except Exception:
                    expiry_time_str = "N/A"

                try:
                    created_at_str = (
                        d.created_at.strftime("%b %d, %Y") if d.created_at else ""
                    )
                except Exception:
                    created_at_str = ""

                result.append(
                    {
                        "id": str(d.id),
                        "food_type": d.food_type or "Unknown",
                        "category": getattr(d, "category", "General") or "General",
                        "quantity": d.quantity or 0,
                        "expiry_label": expiry_label,
                        "expiry_time": expiry_time_str,
                        "status": current_status,
                        "assigned_volunteer": assigned_volunteer,
                        "created_at": created_at_str,
                    }
                )
            except Exception as inner_e:
                logger.warning(f"Error processing donation {d.id}: {inner_e}")
                continue

    except Exception as e:
        logger.error(f"Error fetching inventory: {e}")
        return []

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  POST /ngo/volunteers/{volunteer_id}/approve  – Approve Volunteer
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/volunteers/{volunteer_id}/approve")
def approve_volunteer(
    volunteer_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Approves a volunteer request for this NGO.
    Changes volunteer_status to 'approved'.
    """
    if current_user.role != models.RoleEnum.NGO:
        raise HTTPException(status_code=403, detail="Not authorized")
    # BUG-4 Fix: parse string volunteer_id to UUID before querying UUID column
    try:
        vol_uuid = uuid.UUID(volunteer_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid volunteer ID format")
    volunteer = (
        db.query(models.User)
        .filter(
            models.User.id == vol_uuid,
            models.User.ngo_id == current_user.id,
            models.User.role == models.RoleEnum.VOLUNTEER,
        )
        .first()
    )

    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found for this NGO")

    if not volunteer.ngo_id:
        volunteer.ngo_id = current_user.id

    volunteer.volunteer_status = "approved"
    volunteer.status = "approved"
    volunteer.availability = "available"
    volunteer.is_active = True
    db.commit()
    db.refresh(volunteer)

    return {"success": True, "message": "Volunteer successfully approved."}


# ─────────────────────────────────────────────────────────────────────────────
#  POST /ngo/volunteers/{volunteer_id}/reject  – Reject Volunteer
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/volunteers/{volunteer_id}/reject")
def reject_volunteer(
    volunteer_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Rejects a volunteer request for this NGO.
    Changes volunteer_status to 'rejected'.
    """
    if current_user.role != models.RoleEnum.NGO:
        raise HTTPException(status_code=403, detail="Not authorized")
    # BUG-5 Fix: parse string volunteer_id to UUID before querying UUID column
    try:
        vol_uuid = uuid.UUID(volunteer_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid volunteer ID format")
    volunteer = (
        db.query(models.User)
        .filter(
            models.User.id == vol_uuid,
            models.User.ngo_id == current_user.id,
            models.User.role == models.RoleEnum.VOLUNTEER,
        )
        .first()
    )

    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found for this NGO")

    volunteer.volunteer_status = "rejected"
    volunteer.status = "rejected"
    # Alternatively, you could clear ngo_id so they can apply elsewhere,
    # but the rule says explicitly 'rejected' status.
    db.commit()
    db.refresh(volunteer)
    return {"success": True, "message": "Volunteer successfully rejected."}


# ─────────────────────────────────────────────────────────────────────────────
#  GET /ngo/delivery-tracking  – Delivery Tracking Tab
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/delivery-tracking")
def get_delivery_tracking(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Returns ALL donations for the current NGO with status IN:
    ACCEPTED, ASSIGNED, PICKED_UP, IN_PROGRESS
    """
    logger.info(
        f"get_delivery_tracking called by user {current_user.id}, role: {current_user.role}"
    )
    try:
        if current_user.role != models.RoleEnum.NGO:
            logger.warning(
                f"User {current_user.id} role {current_user.role} is not NGO, returning []"
            )
            return []

        donations = (
            db.query(models.Donation)
            .filter(models.Donation.ngo_id == current_user.id)
            .all()
        )

        filtered = []
        for d in donations:
            if d.status in [
                models.DonationStatusEnum.ACCEPTED,
                models.DonationStatusEnum.ASSIGNED,
                models.DonationStatusEnum.CLAIMED,
                models.DonationStatusEnum.IN_PROGRESS,
                models.DonationStatusEnum.OUT_FOR_DELIVERY,
            ]:
                filtered.append(d)
                logger.info(f"  - donation {d.id}: status matches = {d.status}")
            else:
                logger.info(f"  - donation {d.id}: status = {d.status} (not included)")

        donations = filtered

        logger.info(
            f"get_delivery_tracking: found {len(donations)} donations with matching status for NGO {current_user.id}"
        )

        ngo_profile = current_user.profile
        ngo_name = (
            ngo_profile.name
            if ngo_profile and ngo_profile.name
            else (current_user.name or current_user.email.split("@")[0])
        )
        ngo_latitude = ngo_profile.latitude if ngo_profile else None
        ngo_longitude = ngo_profile.longitude if ngo_profile else None
        ngo_address = ngo_profile.address if ngo_profile else None

        result = []
        for d in donations:
            volunteer_id = None
            delivery_id = None
            status_val = d.status.value if hasattr(d.status, "value") else str(d.status)

            if d.delivery:
                delivery_id = str(d.delivery.id)
                volunteer_id = (
                    str(d.delivery.volunteer_id) if d.delivery.volunteer_id else None
                )
                status_val = (
                    d.delivery.status.value
                    if hasattr(d.delivery.status, "value")
                    else str(d.delivery.status)
                )
            elif d.volunteer_id:
                volunteer_id = str(d.volunteer_id)

            result.append(
                {
                    "id": str(d.id),
                    "donation_id": str(d.id),
                    "delivery_id": delivery_id,
                    "ngo_id": str(d.ngo_id) if d.ngo_id else None,
                    "food_type": d.food_type,
                    "quantity": d.quantity,
                    "status": status_val,
                    "volunteer_id": volunteer_id,
                    "latitude": d.latitude,
                    "longitude": d.longitude,
                    "pickup_latitude": d.pickup_latitude,
                    "pickup_longitude": d.pickup_longitude,
                    "pickup_location": d.pickup_location or d.pickup_address,
                    "ngo_name": ngo_name,
                    "ngo_latitude": ngo_latitude,
                    "ngo_longitude": ngo_longitude,
                    "ngo_address": ngo_address,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
            )

        logger.debug(
            "GET /ngo/delivery-tracking | NGO=%s, donations=%s",
            current_user.id,
            len(result),
        )
        return result
    except Exception as e:
        logger.exception("Error in get_delivery_tracking: %s", str(e))
        return []


@router.get("/distribution-records")
def get_distribution_records(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Returns tested donations ready for distribution (decision = 'distribute' or 'urgent').
    This ensures donations must go through Food Testing first before appearing in Distribution.
    """
    if current_user.role != models.RoleEnum.NGO:
        return []

    from sqlalchemy import text as _t

    try:
        rows = db.execute(
            _t(
                """
                SELECT id, food_type, quantity, food_quality, decision,
                       tested_at, remarks, image_url, created_at, donor_id,
                       total_duration, start_time, category
                FROM donations
                WHERE ngo_id  = :ngo_id
                  AND decision IN ('distribute', 'urgent')
                  AND food_quality IS NOT NULL
                ORDER BY
                  CASE WHEN decision = 'urgent' THEN 0 ELSE 1 END,
                  tested_at DESC NULLS LAST
                LIMIT 200
                """
            ),
            {"ngo_id": str(current_user.id)},
        ).fetchall()
    except Exception as exc:
        logger.exception("get_distribution_records error: %s", str(exc))
        return []

    result = []
    for row in rows:
        result.append(
            {
                "id": str(row[0]),
                "food_type": row[1],
                "quantity": row[2],
                "food_quality": row[3],
                "decision": row[4],
                "tested_at": row[5].isoformat() if row[5] else None,
                "remarks": row[6],
                "image_url": row[7],
                "created_at": row[8].isoformat() if row[8] else None,
                "status": "completed",
                "completed_at": row[5].strftime("%Y-%m-%d %H:%M:%S")
                if row[5]
                else None,
                "total_duration": row[10],
                "start_time": row[11].isoformat() if row[11] else None,
                "category": row[12] or "General",
            }
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  GET /ngo/received-donations  – Donations received & ready for food testing
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/received-donations")
def get_received_donations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Returns donations that have been COMPLETED (received by NGO) and are
    eligible for the Food Testing workflow.  A donation is considered
    'received' once its status is COMPLETED and it belongs to this NGO.
    To avoid re-listing already-tested items, donations whose food_quality
    column is already set are excluded from this list.
    """
    if current_user.role != models.RoleEnum.NGO:
        return []

    from sqlalchemy import text as _t

    try:
        donations = (
            db.query(models.Donation)
            .filter(
                models.Donation.ngo_id == current_user.id,
                models.Donation.status == models.DonationStatusEnum.COMPLETED,
                models.Donation.food_quality.is_(None),
            )
            .order_by(models.Donation.created_at.desc())
            .limit(100)
            .all()
        )
    except Exception as exc:
        logger.exception("Error in get_received_donations: %s", str(exc))
        return []

    result = []
    for d in donations:
        img_url = getattr(d, "image_url", None)
        if not img_url and d.donor and d.donor.profile:
            img_url = getattr(d.donor.profile, "image_url", None)

        donor_name = None
        if d.donor:
            dp = d.donor.profile
            donor_name = (dp.name if dp else None) or d.donor.email.split("@")[0]

        result.append(
            {
                "id": str(d.id),
                "food_type": d.food_type,
                "quantity": d.quantity,
                "category": getattr(d, "category", "General") or "General",
                "donor_name": donor_name,
                "image_url": img_url,
                "food_quality": None,
                "decision": None,
                "tested_at": None,
                "remarks": None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  POST /ngo/donations/{donation_id}/test-food  – Submit food-quality test
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/donations/{donation_id}/test-food")
def test_food(
    donation_id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    NGO submits a food-quality test for a received donation.

    Body (JSON):
        quality  : "fresh" | "moderate" | "spoiled"
        remarks  : str (optional)

    Decision logic:
        fresh    → distribute
        moderate → urgent
        spoiled  → rejected
    """
    if current_user.role != models.RoleEnum.NGO:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        import uuid as _uuid

        don_uuid = _uuid.UUID(donation_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid donation ID format")

    donation = (
        db.query(models.Donation)
        .filter(
            models.Donation.id == don_uuid,
            models.Donation.ngo_id == current_user.id,
        )
        .first()
    )
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found for this NGO")

    quality = (body.get("quality") or "").strip().lower()
    if quality not in ("fresh", "moderate", "spoiled"):
        raise HTTPException(
            status_code=422,
            detail="quality must be one of: fresh, moderate, spoiled",
        )
    remarks = (body.get("remarks") or "").strip() or None

    # Derive decision from quality
    if quality == "fresh":
        decision = "distribute"
    elif quality == "moderate":
        decision = "urgent"
    else:
        decision = "rejected"

    # Write to DB using raw SQL so we don't depend on ORM columns being
    # declared (they are added via safe ALTER TABLE migrations in main.py).
    from sqlalchemy import text as _t

    try:
        db.execute(
            _t(
                """
                UPDATE donations
                SET food_quality = :quality,
                    decision      = :decision,
                    tested_by     = :ngo_id,
                    tested_at     = NOW(),
                    remarks       = :remarks,
                    status       = :new_status,
                    volunteer_id = NULL,
                    task_type    = NULL,
                    distribution_status = 'pending'
                WHERE id = :donation_id
                """
            ),
            {
                "quality": quality,
                "decision": decision,
                "ngo_id": str(current_user.id),
                "remarks": remarks,
                "donation_id": str(don_uuid),
                "new_status": models.DonationStatusEnum.READY_FOR_DISTRIBUTION.value,
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("test_food DB error: %s", str(exc))
        raise HTTPException(status_code=500, detail="Could not save test result")

    # Create a notification about the test outcome
    try:
        label_map = {
            "distribute": "Food marked for Distribution ✅",
            "urgent": "Food marked for Urgent Delivery ⚠️",
            "rejected": "Food marked as Waste / Rejected ❌",
        }
        notif = models.Notification(
            user_id=current_user.id,
            message=label_map.get(decision, "Food test completed"),
            notification_type="info",
        )
        db.add(notif)
        db.commit()
    except Exception:
        pass  # notifications are non-critical

    return {
        "success": True,
        "message": "Food tested successfully",
        "decision": decision,
        "quality": quality,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  GET /ngo/distribution  – Donations ready for distribution (fresh / urgent)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/distribution")
def get_distribution_queue(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Returns tested donations whose decision is 'distribute' or 'urgent'.
    These are the items the NGO should distribute to beneficiaries.
    """
    if current_user.role != models.RoleEnum.NGO:
        return []

    from sqlalchemy import text as _t

    try:
        rows = db.execute(
            _t(
                """
                SELECT d.id, d.food_type, d.quantity, d.food_quality, d.decision,
                       d.tested_at, d.remarks, d.image_url, d.created_at, d.donor_id,
                       d.total_duration, d.start_time, d.category, d.volunteer_id, d.status,
                       d.distribution_otp, d.distribution_status, d.beneficiary_id,
                       u.name as volunteer_name, d.task_type
                FROM donations d
                LEFT JOIN users u ON d.volunteer_id = u.id
                WHERE d.ngo_id  = :ngo_id
                  AND d.decision IN ('distribute', 'urgent')
                  AND d.food_quality IS NOT NULL
                  AND (d.distribution_status IS NULL OR d.distribution_status != 'completed')
                ORDER BY
                  CASE WHEN d.decision = 'urgent' THEN 0 ELSE 1 END,
                  d.tested_at DESC NULLS LAST
                LIMIT 200
                """
            ),
            {"ngo_id": str(current_user.id)},
        ).fetchall()
    except Exception as exc:
        logger.exception("get_distribution_queue error: %s", str(exc))
        return []

    result = []
    for row in rows:
        result.append(
            {
                "id": str(row[0]),
                "food_type": row[1],
                "quantity": row[2],
                "food_quality": row[3],
                "decision": row[4],
                "tested_at": row[5].isoformat() if row[5] else None,
                "remarks": row[6],
                "image_url": row[7],
                "created_at": row[8].isoformat() if row[8] else None,
                "total_duration": row[10],
                "start_time": row[11].isoformat() if row[11] else None,
                "category": row[12] or "General",
                "volunteer_id": str(row[13]) if row[13] else None,
                "status": row[14],
                "distribution_otp": row[15],
                "distribution_status": row[16],
                "beneficiary_id": str(row[17]) if row[17] else None,
                "volunteer_name": row[18] if row[19] == "distribution" else None,
                "assigned_partner_id": str(row[13]) if (row[13] and row[19] == "distribution") else None,
                "assigned_partner_name": row[18] if row[19] == "distribution" else None,
                "task_type": row[19]
            }
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  GET /ngo/waste  – Rejected / spoiled donations
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/waste")
def get_waste_list(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Returns tested donations whose decision is 'rejected' (spoiled food).
    These are items that could not be safely distributed.
    """
    if current_user.role != models.RoleEnum.NGO:
        return []

    from sqlalchemy import text as _t

    try:
        rows = db.execute(
            _t(
                """
                SELECT id, food_type, quantity, food_quality, decision,
                       tested_at, remarks, image_url, created_at
                FROM donations
                WHERE ngo_id  = :ngo_id
                  AND decision = 'rejected'
                  AND food_quality IS NOT NULL
                ORDER BY tested_at DESC NULLS LAST
                LIMIT 200
                """
            ),
            {"ngo_id": str(current_user.id)},
        ).fetchall()
    except Exception as exc:
        logger.exception("get_waste_list error: %s", str(exc))
        return []

    result = []
    for row in rows:
        result.append(
            {
                "id": str(row[0]),
                "food_type": row[1],
                "quantity": row[2],
                "food_quality": row[3],
                "decision": row[4],
                "tested_at": row[5].isoformat() if row[5] else None,
                "remarks": row[6],
                "image_url": row[7],
                "created_at": row[8].isoformat() if row[8] else None,
            }
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  POST /ngo/distribution/assign – AI-powered distribution assignment
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/distribution/assign")
def assign_distribution_partner(
    donation_id: str,
    beneficiary_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Assign delivery partner to a distribution using AI scoring.

    Integrates with Food Testing Decision:
    - decision='urgent' → is_urgent=True (prioritize nearest partner)
    - decision='distribute' → is_urgent=False (balanced scoring)

    Returns partner info with AI reason for the assignment.
    """
    if current_user.role != models.RoleEnum.NGO:
        raise HTTPException(
            status_code=403, detail="Only NGOs can assign distribution partners"
        )

    try:
        don_uuid = uuid.UUID(donation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid donation ID format")

    try:
        donation = (
            db.query(models.Donation)
            .filter(
                models.Donation.id == don_uuid,
                models.Donation.ngo_id == current_user.id,
            )
            .first()
        )
        if not donation:
            raise HTTPException(
                status_code=404, detail="Donation not found for this NGO"
            )

        # Get decision safely - may be None if not tested yet
        decision = getattr(donation, "decision", None)

        if decision not in ("distribute", "urgent"):
            raise HTTPException(
                status_code=400,
                detail="Donation must be tested and approved for distribution",
            )

        is_urgent = decision == "urgent"

        target_lat = donation.pickup_latitude or donation.latitude
        target_lng = donation.pickup_longitude or donation.longitude

        if target_lat is None or target_lng is None:
            raise HTTPException(
                status_code=400, detail="Donation location not available"
            )

        from app.services.ai_service import SmartAssignmentService

        result = SmartAssignmentService.assign_best_partner(
            db=db,
            target_lat=target_lat,
            target_lng=target_lng,
            ngo_id=current_user.id,
            is_urgent=is_urgent,
            max_radius_km=20,
        )

        if not result:
            raise HTTPException(
                status_code=400,
                detail="No Delivery Partner available nearby. Try manual assignment.",
            )

        if beneficiary_id:
            try:
                donation.beneficiary_id = uuid.UUID(beneficiary_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid beneficiary ID format")

        import secrets
        donation.task_type = "distribution"
        donation.distribution_status = "in_progress"
        donation.distribution_otp = f"{secrets.randbelow(10000):04d}"

        assignment = donation_service_assign(
            db=db,
            donation_id=don_uuid,
            ngo_id=current_user.id,
            volunteer_id=result["partner_id"],
        )

        if not assignment:
            raise HTTPException(status_code=500, detail="Failed to assign volunteer")

        return {
            "success": True,
            "donation_id": str(donation_id),
            "partner_id": str(result["partner_id"]),
            "partner_name": result["name"],
            "distance_km": result["distance_km"],
            "score": result["score"],
            "confidence": result["confidence"],
            "reason": result["reason"],
            "is_urgent": is_urgent,
            "assignment_type": "ai",
            "distribution_otp": donation.distribution_otp,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("assign_distribution_partner error: %s", str(exc))
        raise HTTPException(
            status_code=500, detail="Internal server error: " + str(exc)
        )


# ─────────────────────────────────────────────────────────────────────────────
#  POST /ngo/distribution/assign-manual – Manual partner assignment
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/distribution/assign-manual")
def assign_distribution_partner_manual(
    donation_id: str,
    volunteer_id: str,
    beneficiary_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Manually assign a delivery partner to a distribution.

    Request params:
    - donation_id: UUID of the donation to assign
    - volunteer_id: UUID of the volunteer to assign
    """
    if current_user.role != models.RoleEnum.NGO:
        raise HTTPException(
            status_code=403, detail="Only NGOs can assign distribution partners"
        )

    try:
        don_uuid = uuid.UUID(donation_id)
        vol_uuid = uuid.UUID(volunteer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    try:
        donation = (
            db.query(models.Donation)
            .filter(
                models.Donation.id == don_uuid,
                models.Donation.ngo_id == current_user.id,
            )
            .first()
        )
        if not donation:
            raise HTTPException(
                status_code=404, detail="Donation not found for this NGO"
            )

        # Check if already assigned (has volunteer_id)
        # Note: if status is READY_FOR_DISTRIBUTION, volunteer_id is leftover from the pickup leg.
        if donation.status != models.DonationStatusEnum.READY_FOR_DISTRIBUTION and donation.volunteer_id:
            raise HTTPException(
                status_code=400, detail="This donation already has a partner assigned"
            )

        # Verify volunteer exists and belongs to this NGO
        volunteer = (
            db.query(models.User)
            .filter(
                models.User.id == vol_uuid,
                models.User.ngo_id == current_user.id,
                models.User.role == models.RoleEnum.VOLUNTEER,
            )
            .first()
        )
        if not volunteer:
            raise HTTPException(
                status_code=400,
                detail="Invalid volunteer or volunteer not in your team",
            )

        # Verify volunteer is available
        if volunteer.availability and volunteer.availability.lower() not in (
            "available",
            "",
        ):
            raise HTTPException(
                status_code=400,
                detail="Volunteer is not available. Please select an available volunteer.",
            )

        if beneficiary_id:
            try:
                donation.beneficiary_id = uuid.UUID(beneficiary_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid beneficiary ID format")

        import secrets
        donation.task_type = "distribution"
        donation.distribution_status = "in_progress"
        donation.distribution_otp = f"{secrets.randbelow(10000):04d}"

        # Assign the volunteer manually
        assignment = donation_service_assign(
            db=db,
            donation_id=don_uuid,
            ngo_id=current_user.id,
            volunteer_id=vol_uuid,
        )

        if not assignment:
            raise HTTPException(status_code=500, detail="Failed to assign volunteer")

        # Get volunteer name for response
        volunteer_name = (
            volunteer.profile.name
            if getattr(volunteer, "profile", None)
            else volunteer.email.split("@")[0]
        )

        return {
            "success": True,
            "donation_id": str(donation_id),
            "partner_id": str(vol_uuid),
            "partner_name": volunteer_name,
            "assignment_type": "manual",
            "distribution_otp": donation.distribution_otp,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("assign_distribution_partner_manual error: %s", str(exc))
        raise HTTPException(
            status_code=500, detail="Internal server error: " + str(exc)
        )

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.domain import models, schemas
from app.interfaces.deps import get_db, get_current_active_user, RoleChecker
from app.core.constants import (
    CERTIFICATE_MIN_DONATIONS,
    RELIABILITY_POINTS_PER_DELIVERY,
    WASTE_REDUCTION_KG_PER_UNIT,
    MEALS_PER_UNIT,
)
from app.services.ai_service import AIService

router = APIRouter()


@router.get("/stats", response_model=dict)
def get_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    """
    Get system stats: NGO, Donor, Volunteer counts.
    """

    ngo_count = (
        db.query(models.User).filter(models.User.role == models.RoleEnum.NGO).count()
    )
    donor_count = (
        db.query(models.User).filter(models.User.role == models.RoleEnum.DONOR).count()
    )
    volunteer_count = (
        db.query(models.User)
        .filter(models.User.role == models.RoleEnum.VOLUNTEER)
        .count()
    )

    active_donations = (
        db.query(models.Donation)
        .filter(
            models.Donation.status.in_(
                [
                    models.DonationStatusEnum.PENDING,
                    models.DonationStatusEnum.ACCEPTED,
                    models.DonationStatusEnum.IN_PROGRESS,
                ]
            )
        )
        .count()
    )

    completed_donations = (
        db.query(models.Donation)
        .filter(models.Donation.status == models.DonationStatusEnum.COMPLETED)
        .count()
    )

    pending_approvals = (
        db.query(models.User)
        .filter(
            models.User.role == models.RoleEnum.NGO, models.User.is_verified == False
        )
        .count()
    )

    pending_volunteers = (
        db.query(models.User)
        .filter(
            models.User.role == models.RoleEnum.VOLUNTEER,
            models.User.volunteer_status.ilike("pending"),
        )
        .count()
    )

    approved_volunteers = (
        db.query(models.User)
        .filter(
            models.User.role == models.RoleEnum.VOLUNTEER,
            models.User.volunteer_status == "approved",
        )
        .count()
    )

    rejected_volunteers = (
        db.query(models.User)
        .filter(
            models.User.role == models.RoleEnum.VOLUNTEER,
            models.User.volunteer_status == "rejected",
        )
        .count()
    )

    # Calculate average delivery time from completed donations
    avg_delivery_time = 0
    completed_with_time = (
        db.query(models.Donation)
        .filter(
            models.Donation.status == models.DonationStatusEnum.COMPLETED,
            models.Donation.total_duration.isnot(None),
        )
        .all()
    )
    if completed_with_time:
        total_mins = sum(
            d.total_duration for d in completed_with_time if d.total_duration
        )
        avg_delivery_time = round(total_mins / len(completed_with_time), 1)

    return {
        "ngo_count": ngo_count,
        "donor_count": donor_count,
        "volunteer_count": volunteer_count,
        "pending_volunteers": pending_volunteers,
        "approved_volunteers": approved_volunteers,
        "rejected_volunteers": rejected_volunteers,
        "total_users": ngo_count + donor_count + volunteer_count,
        "active_donations": active_donations,
        "completed_donations": completed_donations,
        "pending_approvals": pending_approvals,
        "avgDeliveryTime": avg_delivery_time,
    }


@router.get("/pending-ngos", response_model=List[schemas.UserResponse])
def get_pending_ngos(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    """
    List NGOs awaiting approval.
    """

    return (
        db.query(models.User)
        .filter(
            models.User.role == models.RoleEnum.NGO,
            models.User.is_verified == False,
            models.User.is_active == True,
        )
        .all()
    )


@router.post("/approve-ngo/{user_id}", response_model=schemas.UserResponse)
def approve_ngo(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    """
    Approve an NGO.
    """

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_verified = True
    db.commit()
    db.refresh(user)
    return user


@router.post("/reject-ngo/{user_id}", response_model=schemas.UserResponse)
def reject_ngo(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    """
    Reject an NGO registration. Sets is_active=False so they cannot log in.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != models.RoleEnum.NGO:
        raise HTTPException(status_code=400, detail="User is not an NGO")

    user.is_active = False
    user.is_verified = False
    db.commit()
    db.refresh(user)
    return user


@router.get("/volunteers/performance")
def get_volunteer_performance(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    """
    Returns performance stats for all volunteers based on actual deliveries.
    """
    from sqlalchemy import func
    from datetime import datetime

    volunteers = (
        db.query(models.User)
        .filter(models.User.role == models.RoleEnum.VOLUNTEER)
        .all()
    )

    results = []
    for v in volunteers:
        name = v.profile.name if v.profile else (v.name or v.email.split("@")[0])

        # Count completed deliveries for this volunteer
        completed = (
            db.query(models.Delivery)
            .filter(
                models.Delivery.volunteer_id == v.id,
                models.Delivery.status == models.DeliveryStatusEnum.DELIVERED,
            )
            .all()
        )
        total_deliveries = len(completed)

        # Compute average delivery time (assigned_at → completed_at) in minutes
        avg_time_mins = None
        times = []
        for d in completed:
            if d.assigned_at and d.completed_at:
                delta = (d.completed_at - d.assigned_at).total_seconds() / 60.0
                times.append(delta)
        if times:
            avg_time_mins = round(sum(times) / len(times), 1)

        results.append(
            {
                "volunteer_id": str(v.id),
                "name": name,
                "email": v.email,
                "status": v.volunteer_status or "pending",
                "total_deliveries": total_deliveries,
                "avg_delivery_time_mins": avg_time_mins,
                "rating": round(v.rating or 5.0, 1),
                "reliability_score": min(
                    100, total_deliveries * RELIABILITY_POINTS_PER_DELIVERY
                )
                if total_deliveries > 0
                else 0,
            }
        )

    results.sort(key=lambda x: x["total_deliveries"], reverse=True)
    return results


@router.get("/suspicious-users", response_model=List[schemas.FraudAlertResponse])
def get_suspicious_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    """
    AI Module 4: Fraud Detection. Returns users with a trust score < 70.
    """
    users = db.query(models.User).filter(models.User.trust_score < 70).all()

    results = []
    for u in users:
        results.append(
            {
                "user_id": u.id,
                "email": u.email,
                "role": u.role.value,
                "trust_score": u.trust_score,
                "created_at": u.created_at,
            }
        )
    return results


@router.get("/demand-heatmap")
def get_demand_heatmap(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    """
    AI Module 5: Donation Demand Prediction (Heatmap Data).
    Returns live lat/lng coordinates derived from donation activity.
    """
    return AIService.get_hunger_heatmap(db)


@router.get("/impact-analytics", response_model=schemas.ImpactAnalyticsResponse)
def get_impact_analytics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    """
    AI Module 6: Impact Analytics AI.
    """
    from sqlalchemy import func

    # 1 unit = configurable kg waste reduced = configurable meals served
    completed_donations = (
        db.query(models.Donation)
        .filter(models.Donation.status == models.DonationStatusEnum.COMPLETED)
        .all()
    )
    total_units = sum(d.quantity for d in completed_donations)

    total_waste_reduced = total_units * WASTE_REDUCTION_KG_PER_UNIT
    total_meals_served = total_units * MEALS_PER_UNIT

    # Top volunteers by completed deliveries
    completed_donations_ids = [d.id for d in completed_donations]
    top_vols = []
    if completed_donations_ids:
        top_vols = (
            db.query(
                models.Delivery.volunteer_id,
                func.count(models.Delivery.id).label("count"),
            )
            .filter(models.Delivery.donation_id.in_(completed_donations_ids))
            .group_by(models.Delivery.volunteer_id)
            .order_by(func.count(models.Delivery.id).desc())
            .limit(3)
            .all()
        )

    top_volunteers_list = []
    for vol_id, count in top_vols:
        user = db.query(models.User).filter(models.User.id == vol_id).first()
        name = user.profile.name if user and user.profile else "Unknown Volunteer"
        top_volunteers_list.append({"name": name, "deliveries": count})

    return {
        "total_waste_reduced_kg": round(float(total_waste_reduced), 2),
        "total_meals_served": int(total_meals_served),
        "top_volunteers": top_volunteers_list,
    }


@router.get("/system-users", response_model=List[schemas.AdminSystemUserResponse])
def get_system_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    results = []
    for u in users:
        name = u.profile.name if u.profile else u.email.split("@")[0]
        status = "Active" if u.is_active else "Suspended"
        if u.role == models.RoleEnum.NGO and not u.is_verified:
            status = "Pending"

        results.append(
            {
                "id": u.id,
                "name": name,
                "email": u.email,
                "role": u.role.value,
                "join_date": u.created_at,
                "status": status,
            }
        )
    return results


@router.get(
    "/system-donations", response_model=List[schemas.AdminSystemDonationResponse]
)
def get_system_donations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    donations = (
        db.query(models.Donation).order_by(models.Donation.created_at.desc()).all()
    )
    results = []
    for d in donations:
        donor_name = (
            d.donor.profile.name if d.donor and d.donor.profile else "Unknown Donor"
        )

        volunteer_name = None
        if d.delivery and d.delivery.volunteer:
            volunteer_name = (
                d.delivery.volunteer.profile.name
                if d.delivery.volunteer.profile
                else "Unknown Vol"
            )

        # Determine pickup location
        pickup_location = (
            d.donor.profile.address
            if d.donor and d.donor.profile and d.donor.profile.address
            else "Donor Address"
        )

        # Get NGO name
        ngo_name = None
        if d.ngo and d.ngo.profile:
            ngo_name = d.ngo.profile.name
        elif d.ngo:
            ngo_name = d.ngo.email.split("@")[0]

        results.append(
            {
                "id": d.id,
                "donor_name": donor_name,
                "food_type": d.food_type,
                "quantity": d.quantity,
                "pickup_location": pickup_location,
                "assigned_volunteer": volunteer_name,
                "ngo_name": ngo_name,
                "delivery_status": d.status.value.lower()
                if hasattr(d.status, "value")
                else str(d.status).lower(),
            }
        )
    return results


@router.get(
    "/activity-timeline", response_model=List[schemas.AdminActivityTimelineResponse]
)
def get_activity_timeline(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    activities = []

    # Recent users
    recent_users = (
        db.query(models.User).order_by(models.User.created_at.desc()).limit(10).all()
    )
    for u in recent_users:
        activities.append(
            {
                "id": u.id,
                "activity_type": "User",
                "message": f"New {u.role.value} registered: {u.email}",
                "timestamp": u.created_at,
            }
        )

    # Recent donations
    recent_donations = (
        db.query(models.Donation)
        .order_by(models.Donation.created_at.desc())
        .limit(10)
        .all()
    )
    for d in recent_donations:
        donor_name = d.donor.profile.name if d.donor and d.donor.profile else "A donor"
        activities.append(
            {
                "id": d.id,
                "activity_type": "Donation",
                "message": f"Donation created by {donor_name}: {d.quantity} units of {d.food_type}",
                "timestamp": d.created_at,
            }
        )

    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    return activities[:15]


@router.get("/analytics/monthly-donations")
def get_monthly_donations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    from sqlalchemy import extract, func
    import calendar

    results = (
        db.query(
            extract("month", models.Donation.created_at).label("month"),
            func.count(models.Donation.id).label("count"),
        )
        .group_by(extract("month", models.Donation.created_at))
        .order_by(extract("month", models.Donation.created_at))
        .all()
    )

    months = [
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
    monthly_data = {m: 0 for m in months}

    for r in results:
        month_num = int(r[0]) if r[0] is not None else 1
        if 1 <= month_num <= 12:
            monthly_data[calendar.month_abbr[month_num]] = r[1]

    labels = list(monthly_data.keys())
    data = list(monthly_data.values())

    return {
        "monthly_donations": {
            "labels": labels,
            "datasets": [{"label": "Donations Generated", "data": data}],
        }
    }


@router.get("/analytics/volunteer-reliability")
def get_volunteer_reliability(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    volunteers = (
        db.query(models.User)
        .filter(models.User.role == models.RoleEnum.VOLUNTEER)
        .all()
    )

    labels = []
    data = []

    for vol in volunteers:
        assigned = (
            db.query(models.Delivery)
            .filter(models.Delivery.volunteer_id == vol.id)
            .count()
        )
        completed = (
            db.query(models.Delivery)
            .filter(
                models.Delivery.volunteer_id == vol.id,
                models.Delivery.status == models.DeliveryStatusEnum.DELIVERED,
            )
            .count()
        )

        rel = (completed / assigned * 100) if assigned > 0 else 0

        if assigned > 0:
            name = vol.profile.name if vol.profile else vol.email.split("@")[0]
            labels.append(name)
            data.append(round(rel, 1))

    # Top 10 by reliability
    sorted_pairs = sorted(zip(labels, data), key=lambda x: x[1], reverse=True)[:10]

    return {
        "volunteer_stats": {
            "labels": [label for label, _ in sorted_pairs],
            "datasets": [
                {"label": "Reliability (%)", "data": [val for _, val in sorted_pairs]}
            ],
        }
    }


@router.get("/analytics/ngo-performance")
def get_ngo_performance(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    ngos = (
        db.query(models.User)
        .filter(
            models.User.role == models.RoleEnum.NGO,
            models.User.is_active == True,
            models.User.is_verified == True,
        )
        .all()
    )

    labels = []
    data = []

    for ngo in ngos:
        completed = (
            db.query(models.Delivery)
            .filter(
                models.Delivery.ngo_id == ngo.id,
                models.Delivery.status == models.DeliveryStatusEnum.DELIVERED,
            )
            .count()
        )

        if completed > 0:
            name = ngo.profile.name if ngo.profile else ngo.email.split("@")[0]
            labels.append(name)
            data.append(completed)

    # Top 5 NGOs
    sorted_pairs = sorted(zip(labels, data), key=lambda x: x[1], reverse=True)[:5]

    return {
        "ngo_performance": {
            "labels": [label for label, _ in sorted_pairs],
            "datasets": [
                {
                    "label": "Completed Deliveries",
                    "data": [val for _, val in sorted_pairs],
                }
            ],
        }
    }


@router.get("/analytics/heatmap")
def get_analytics_heatmap(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    donations = db.query(models.Donation).all()
    points = []
    for d in donations:
        if d.latitude and d.longitude:
            points.append({"lat": d.latitude, "lng": d.longitude, "weight": 1.0})
        elif d.pickup_latitude and d.pickup_longitude:
            points.append(
                {"lat": d.pickup_latitude, "lng": d.pickup_longitude, "weight": 1.0}
            )
    return points


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(RoleChecker([models.RoleEnum.ADMIN])),
):
    """
    Remove a user from the system permanently.
    Admin accounts cannot be deleted.
    """
    import uuid

    try:
        uid = uuid.UUID(str(user_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user_to_delete = db.query(models.User).filter(models.User.id == uid).first()

    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")

    if user_to_delete.role == models.RoleEnum.ADMIN:
        return {"success": False, "message": "Admin accounts cannot be removed."}

    # Manual cascading delete to avoid IntegrityError

    # 1. Delete Profile
    db.query(models.Profile).filter(models.Profile.user_id == uid).delete(
        synchronize_session=False
    )

    # BUG-12 Fix: Delete Notifications linked to this user (FK: notifications.user_id → users.id)
    # Missing this caused an IntegrityError when the user row was deleted.
    db.query(models.Notification).filter(models.Notification.user_id == uid).delete(
        synchronize_session=False
    )

    # BUG-12 Fix: Delete LocationTracking rows where volunteer_id = uid
    # (distinct from VolunteerLocation — both tables reference users.id)
    db.query(models.LocationTracking).filter(
        models.LocationTracking.volunteer_id == uid
    ).delete(synchronize_session=False)

    # 2. Clean up Volunteer References
    db.query(models.VolunteerLocation).filter(
        models.VolunteerLocation.volunteer_id == uid
    ).delete(synchronize_session=False)
    deliveries_vol = (
        db.query(models.Delivery).filter(models.Delivery.volunteer_id == uid).all()
    )
    for d in deliveries_vol:
        donation = (
            db.query(models.Donation)
            .filter(models.Donation.id == d.donation_id)
            .first()
        )
        if donation and donation.status != models.DonationStatusEnum.COMPLETED:
            donation.status = models.DonationStatusEnum.PENDING
            donation.volunteer_id = None
            donation.delivery_status = "pending"
        db.delete(d)

    linked_dons_vol = (
        db.query(models.Donation).filter(models.Donation.volunteer_id == uid).all()
    )
    for don in linked_dons_vol:
        don.volunteer_id = None
        if don.status != models.DonationStatusEnum.COMPLETED:
            don.status = models.DonationStatusEnum.PENDING
            don.delivery_status = "pending"
            don.otp_code = None

    # 3. Clean up NGO References
    volunteers = db.query(models.User).filter(models.User.ngo_id == uid).all()
    for v in volunteers:
        v.ngo_id = None
        v.volunteer_status = "pending"

    deliveries_ngo = (
        db.query(models.Delivery).filter(models.Delivery.ngo_id == uid).all()
    )
    for d in deliveries_ngo:
        donation = (
            db.query(models.Donation)
            .filter(models.Donation.id == d.donation_id)
            .first()
        )
        if donation and donation.status != models.DonationStatusEnum.COMPLETED:
            donation.status = models.DonationStatusEnum.PENDING
            donation.ngo_id = None
            donation.volunteer_id = None
            donation.delivery_status = "pending"
        db.delete(d)

    linked_dons_ngo = (
        db.query(models.Donation).filter(models.Donation.ngo_id == uid).all()
    )
    for don in linked_dons_ngo:
        don.ngo_id = None
        don.volunteer_id = None
        if don.status != models.DonationStatusEnum.COMPLETED:
            don.status = models.DonationStatusEnum.PENDING
            don.delivery_status = "pending"
            don.otp_code = None

    # 4. Clean up Donor References (delete their donations + linked deliveries)
    donations = db.query(models.Donation).filter(models.Donation.donor_id == uid).all()
    for don in donations:
        db.query(models.Delivery).filter(models.Delivery.donation_id == don.id).delete(
            synchronize_session=False
        )
        db.delete(don)

    # 5. Flush manual changes & force delete user
    try:
        db.flush()
        db.query(models.User).filter(models.User.id == uid).delete(
            synchronize_session=False
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True, "message": "User removed successfully"}

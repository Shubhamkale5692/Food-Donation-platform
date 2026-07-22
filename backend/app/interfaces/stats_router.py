import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.infrastructure.database import get_db
from app.domain.models import Donation, User, RoleEnum, DonationStatusEnum
from app.interfaces.deps import get_current_active_user, RoleChecker
from datetime import datetime, timezone, timedelta

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/dashboard-summary", response_model=dict)
def get_dashboard_summary(
    db: Session = Depends(get_db),
):
    """
    Returns live statistics for the FoodBridge platform.
    This fulfills the exact counting requirements detailed in the requested task:
    - Meals Delivered: Sum of completed donations
    - Active Donors: Count of users with Donor role
    - Partner NGOs: Count of users with NGO role (where is_verified is True)
    - Volunteers: Count of users with Volunteer role (where is_active is True, simulating isApproved)

    This endpoint is public - no authentication required (for homepage stats strip).
    """
    try:
        # Meals Delivered: Sum of quantity in Donations where status is COMPLETED
        meals_delivered = (
            db.query(func.sum(Donation.quantity))
            .filter(Donation.status == DonationStatusEnum.COMPLETED)
            .scalar()
            or 0
        )

        # Active Donors
        active_donors = db.query(User).filter(User.role == RoleEnum.DONOR).count()

        # Partner NGOs (isApproved equivalent is is_verified)
        partner_ngos = (
            db.query(User)
            .filter(User.role == RoleEnum.NGO, User.is_verified == True)  # noqa: E712
            .count()
        )

        # Volunteers
        volunteers = (
            db.query(User)
            .filter(User.role == RoleEnum.VOLUNTEER, User.is_active == True)  # noqa: E712
            .count()
        )

        return {
            "success": True,
            "data": {
                "mealsDelivered": meals_delivered,
                "activeDonors": active_donors,
                "partnerNGOs": partner_ngos,
                "volunteers": volunteers,
            },
        }
    except Exception as e:
        logger.error(f"Failed to fetch dashboard summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch statistics",
        )


@router.get("/daily")
def get_daily_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([RoleEnum.NGO, RoleEnum.ADMIN])),
):
    """
    Returns daily statistics (counts only).
    For NGOs: returns their daily stats.
    For Admins: returns system-wide daily stats.
    """
    today = datetime.now(timezone.utc).date()
    start_of_day = datetime.combine(today, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    if current_user.role == RoleEnum.NGO:
        donations = (
            db.query(Donation)
            .filter(
                Donation.ngo_id == current_user.id,
                Donation.created_at >= start_of_day,
            )
            .all()
        )
        completed = sum(
            d.quantity for d in donations if d.status == DonationStatusEnum.COMPLETED
        )
        total = len(donations)
    else:
        donations = db.query(Donation).filter(Donation.created_at >= start_of_day).all()
        completed = sum(
            d.quantity for d in donations if d.status == DonationStatusEnum.COMPLETED
        )
        total = len(donations)

    return {
        "date": today.isoformat(),
        "total_donations": total,
        "completed_donations": completed,
        "items_distributed": completed,
    }


@router.get("/weekly")
def get_weekly_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([RoleEnum.NGO, RoleEnum.ADMIN])),
):
    """
    Returns weekly statistics (counts only).
    For NGOs: returns their weekly stats.
    For Admins: returns system-wide weekly stats.
    """
    today = datetime.now(timezone.utc).date()
    start_of_week = today - timedelta(days=today.weekday())
    start_datetime = datetime.combine(start_of_week, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    if current_user.role == RoleEnum.NGO:
        donations = (
            db.query(Donation)
            .filter(
                Donation.ngo_id == current_user.id,
                Donation.created_at >= start_datetime,
            )
            .all()
        )
        completed = sum(
            d.quantity for d in donations if d.status == DonationStatusEnum.COMPLETED
        )
        total = len(donations)
    else:
        donations = (
            db.query(Donation).filter(Donation.created_at >= start_datetime).all()
        )
        completed = sum(
            d.quantity for d in donations if d.status == DonationStatusEnum.COMPLETED
        )
        total = len(donations)

    return {
        "week_start": start_of_week.isoformat(),
        "week_end": today.isoformat(),
        "total_donations": total,
        "completed_donations": completed,
        "items_distributed": completed,
    }


@router.get("/export-csv")
def export_donations_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([RoleEnum.NGO, RoleEnum.ADMIN])),
):
    """
    Export donations as CSV for NGO.
    Returns CSV format data that frontend can download.
    """
    if current_user.role == RoleEnum.NGO:
        donations = (
            db.query(Donation)
            .filter(
                Donation.ngo_id == current_user.id,
                Donation.status == DonationStatusEnum.COMPLETED,
            )
            .order_by(Donation.created_at.desc())
            .limit(500)
            .all()
        )
    else:
        donations = (
            db.query(Donation)
            .filter(Donation.status == DonationStatusEnum.COMPLETED)
            .order_by(Donation.created_at.desc())
            .limit(500)
            .all()
        )

    csv_lines = ["ID,Food Type,Quantity,Status,Created At,Delivery Time"]
    for d in donations:
        csv_lines.append(
            f"{d.id},{d.food_type},{d.quantity},{d.status.value},{d.created_at.isoformat() if d.created_at else ''},{d.delivery_time.isoformat() if d.delivery_time else ''}"
        )

    return {
        "csv": "\n".join(csv_lines),
        "count": len(donations),
    }

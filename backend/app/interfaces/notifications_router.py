"""
FoodBridge – Notifications Router
Provides simple notification endpoints for tracking system events.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.domain import models
from app.infrastructure.database import get_db
from app.interfaces.deps import get_current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)


class NotificationCreate(BaseModel):
    message: str
    notification_type: str = "info"


class NotificationResponse(BaseModel):
    id: str
    message: str
    notification_type: str
    is_read: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)


def create_notification(
    db: Session,
    user_id: models.User.id,
    message: str,
    notification_type: str = "info",
) -> models.Notification:
    """Helper to create notification in database"""
    notif = models.Notification(
        user_id=user_id,
        message=message,
        notification_type=notification_type,
    )
    db.add(notif)
    db.commit()
    return notif


@router.get("/", response_model=List[NotificationResponse])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    unread_only: bool = False,
):
    """
    Get notifications for current user.
    By default returns last 50 notifications.
    Use unread_only=true to get only unread notifications.
    """
    query = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    )

    if unread_only:
        query = query.filter(models.Notification.is_read == False)

    notifications = (
        query.order_by(models.Notification.created_at.desc()).limit(50).all()
    )

    result = []
    for n in notifications:
        result.append(
            NotificationResponse(
                id=str(n.id),
                message=n.message,
                notification_type=n.notification_type,
                is_read=n.is_read,
                created_at=n.created_at.isoformat() if n.created_at else "",
            )
        )
    return result


@router.post("/read/{notification_id}")
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Mark a single notification as read"""
    import uuid

    try:
        nid = uuid.UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification ID")

    notif = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == nid,
            models.Notification.user_id == current_user.id,
        )
        .first()
    )

    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    db.commit()

    return {"success": True, "message": "Notification marked as read"}


@router.post("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Mark all notifications as read for current user"""
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()

    return {"success": True, "message": "All notifications marked as read"}


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Get count of unread notifications"""
    count = (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == current_user.id,
            models.Notification.is_read == False,
        )
        .count()
    )

    return {"unread_count": count}

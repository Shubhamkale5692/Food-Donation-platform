import logging
import os
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain import models

logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI
    from fastapi_mail import FastMail, ConnectionConfig
    from fastapi_mail.models import MessageSchema
    from app.core.config import settings
    from pydantic import EmailStr

    conf = ConnectionConfig(
        MAIL_USERNAME=os.getenv("MAIL_USERNAME", "your_email@gmail.com"),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", "app_password"),
        MAIL_FROM=os.getenv("MAIL_FROM", "your_email@gmail.com"),
        MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
        MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
        MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "true").lower() == "true",
        MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "false").lower() == "true",
    )

    EMAIL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"FastAPI-Mail not available: {e}")
    EMAIL_AVAILABLE = False


def get_user_email(db: Session, user_id: UUID) -> Optional[str]:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        return user.email
    return None


async def send_certificate_email(
    user_id: UUID,
    cert_path: str,
    level: str,
    role: str,
):
    if not EMAIL_AVAILABLE:
        logger.warning(
            f"Email not configured, skipping certificate email for user {user_id}"
        )
        return

    from app.infrastructure.database import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found for certificate email")
            return

        user_name = user.name or user.email.split("@")[0]
        user_email = user.email

        role_title = "Donor" if role == "donor" else "Volunteer"

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #f9f9f9; padding: 30px; border-radius: 10px;">
                <h2 style="color: #2C3E50;">🎉 Congratulations {user_name}!</h2>
                <p style="font-size: 16px; color: #34495E;">
                    We are thrilled to inform you that you have achieved <strong>{level}</strong> {role_title} status on FoodBridge!
                </p>
                <p style="font-size: 14px; color: #7F8C8D;">
                    Your dedication to reducing food waste and helping those in need has made a real difference.
                    As a token of our appreciation, please find your certificate attached.
                </p>
                <div style="margin: 20px 0; padding: 15px; background: #E8F6F3; border-left: 4px solid #1ABC9C;">
                    <strong style="color: #16A085;">Achievement Unlocked:</strong> {level} {role_title}
                </div>
                <p style="font-size: 12px; color: #95A5A6; margin-top: 20px;">
                    This is an automated message from FoodBridge. Please do not reply to this email.
                </p>
            </div>
        </body>
        </html>
        """

        attachments = []
        if os.path.exists(cert_path):
            attachments = [cert_path]
        else:
            logger.warning(f"Certificate file not found: {cert_path}")

        message = MessageSchema(
            subject=f"🏆 Your FoodBridge {level} {role_title} Certificate",
            recipients=[user_email],
            body=body_html,
            subtype="html",
            attachments=attachments,
        )

        fm = FastMail(conf)
        await fm.send_message(message)

        cert = (
            db.query(models.Certificate)
            .filter_by(user_id=user_id, role=role, level=level)
            .first()
        )
        if cert:
            cert.email_sent = True
            db.commit()

        logger.info(
            f"Certificate email sent to {user_email} for {level} {role_title} certificate"
        )

    except Exception as e:
        logger.error(f"Failed to send certificate email: {e}")
    finally:
        db.close()

import logging
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from jinja2 import Template
from sqlalchemy.orm import Session

from app.domain import models
from app.core.config import settings

logger = logging.getLogger(__name__)

CERTIFICATE_LEVELS = {
    5: "Bronze",
    10: "Silver",
    25: "Gold",
    50: "Platinum",
}


def get_level(count: int) -> Optional[str]:
    for threshold, level in sorted(CERTIFICATE_LEVELS.items(), reverse=True):
        if count >= threshold:
            return level
    return None


def get_next_level(count: int) -> Optional[tuple[int, str]]:
    thresholds = sorted(CERTIFICATE_LEVELS.keys())
    for threshold in thresholds:
        if count < threshold:
            return (threshold, CERTIFICATE_LEVELS[threshold])
    return None


DONOR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Lato:wght@300;400;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Lato', sans-serif; }
        .certificate {
            width: 800px;
            height: 600px;
            background: linear-gradient(135deg, #FFF8E7 0%, #FFEFD5 50%, #FFD700 100%);
            border: 8px solid #B8860B;
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            position: relative;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        .header { margin-bottom: 30px; }
        .logo { font-size: 32px; font-weight: bold; color: #B8860B; font-family: 'Cinzel', serif; }
        .title { font-size: 42px; color: #8B4513; margin: 20px 0; font-family: 'Cinzel', serif; font-weight: 700; }
        .subtitle { font-size: 18px; color: #654321; margin-bottom: 30px; }
        .recipient { font-size: 36px; color: #2C1810; margin: 30px 0; font-family: 'Cinzel', serif; font-weight: 700; }
        .achievement { font-size: 24px; color: #8B4513; margin: 20px 0; }
        .level { font-size: 48px; color: #FFD700; font-family: 'Cinzel', serif; font-weight: 700; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .count { font-size: 20px; color: #654321; margin: 15px 0; }
        .date { font-size: 16px; color: #8B7355; margin-top: 30px; }
        .footer { position: absolute; bottom: 40px; left: 0; right: 0; display: flex; justify-content: space-around; }
        .signature { text-align: center; }
        .sig-line { border-top: 2px solid #8B4513; width: 200px; margin: 10px auto; }
        .sig-name { font-size: 14px; color: #654321; }
        .seal {
            position: absolute;
            bottom: 30px;
            right: 30px;
            width: 100px;
            height: 100px;
            background: radial-gradient(circle, #FFD700 0%, #B8860B 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
            font-weight: bold;
            border: 3px solid #8B4513;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>
    <div class="certificate">
        <div class="header">
            <div class="logo">🍽️ FoodBridge</div>
        </div>
        <h1 class="title">Certificate of Appreciation</h1>
        <p class="subtitle">This certificate is proudly presented to</p>
        <div class="recipient">{{ user_name }}</div>
        <div class="count">For completing <strong>{{ count }}</strong> successful food donations</div>
        <div class="level">{{ level }} Donor</div>
        <div class="date">Issued on {{ date }}</div>
        <div class="footer">
            <div class="signature">
                <div class="sig-line"></div>
                <div class="sig-name">FoodBridge Director</div>
            </div>
            <div class="signature">
                <div class="sig-line"></div>
                <div class="sig-name">Certificate ID: {{ certificate_id }}</div>
            </div>
        </div>
        <div class="seal">NGO<br>Partner</div>
    </div>
</body>
</html>
"""

VOLUNTEER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Lato:wght@300;400;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Lato', sans-serif; }
        .certificate {
            width: 800px;
            height: 600px;
            background: linear-gradient(135deg, #E0F7FA 0%, #B2EBF2 50%, #00BCD4 100%);
            border: 8px solid #00838F;
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            position: relative;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        .header { margin-bottom: 30px; }
        .logo { font-size: 32px; font-weight: bold; color: #00838F; font-family: 'Cinzel', serif; }
        .title { font-size: 42px; color: #006064; margin: 20px 0; font-family: 'Cinzel', serif; font-weight: 700; }
        .subtitle { font-size: 18px; color: #00838F; margin-bottom: 30px; }
        .recipient { font-size: 36px; color: #00363A; margin: 30px 0; font-family: 'Cinzel', serif; font-weight: 700; }
        .achievement { font-size: 24px; color: #006064; margin: 20px 0; }
        .level { font-size: 48px; color: #00BCD4; font-family: 'Cinzel', serif; font-weight: 700; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .count { font-size: 20px; color: #006064; margin: 15px 0; }
        .date { font-size: 16px; color: #546E7A; margin-top: 30px; }
        .footer { position: absolute; bottom: 40px; left: 0; right: 0; display: flex; justify-content: space-around; }
        .signature { text-align: center; }
        .sig-line { border-top: 2px solid #006064; width: 200px; margin: 10px auto; }
        .sig-name { font-size: 14px; color: #546E7A; }
        .seal {
            position: absolute;
            bottom: 30px;
            right: 30px;
            width: 100px;
            height: 100px;
            background: radial-gradient(circle, #00BCD4 0%, #00838F 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
            font-weight: bold;
            border: 3px solid #006064;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>
    <div class="certificate">
        <div class="header">
            <div class="logo">🍽️ FoodBridge</div>
        </div>
        <h1 class="title">Certificate of Service & Appreciation</h1>
        <p class="subtitle">This certificate is proudly presented to</p>
        <div class="recipient">{{ user_name }}</div>
        <div class="count">For completing <strong>{{ count }}</strong> delivery missions</div>
        <div class="level">{{ level }} Volunteer</div>
        <div class="date">Issued on {{ date }}</div>
        <div class="footer">
            <div class="signature">
                <div class="sig-line"></div>
                <div class="sig-name">FoodBridge Director</div>
            </div>
            <div class="signature">
                <div class="sig-line"></div>
                <div class="sig-name">Certificate ID: {{ certificate_id }}</div>
            </div>
        </div>
        <div class="seal">Verified<br>Volunteer</div>
    </div>
</body>
</html>
"""


def get_user_name(db: Session, user_id: UUID) -> str:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user and user.profile and user.profile.name:
        return user.profile.name
    if user and user.name:
        return user.name
    if user:
        return user.email.split("@")[0]
    return "Unknown User"


def generate_certificate_pdf(
    user_id: UUID,
    role: str,
    level: str,
    count: int,
    certificate_id: str,
    db: Session,
) -> str:
    try:
        import pdfkit
    except ImportError:
        logger.warning("pdfkit not installed, returning HTML path")
        return generate_certificate_html(
            user_id, role, level, count, certificate_id, db
        )

    html = generate_certificate_html(user_id, role, level, count, certificate_id, db)

    static_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "static",
        "certificates",
    )
    os.makedirs(static_dir, exist_ok=True)

    file_path = os.path.join(static_dir, f"{certificate_id}.pdf")

    try:
        pdfkit.from_string(
            html, file_path, options={"page-width": "800px", "page-height": "600px"}
        )
        logger.info(f"PDF certificate generated: {file_path}")
    except Exception as e:
        logger.error(f"PDF generation failed: {e}, returning HTML")
        html_path = file_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        return html_path

    return file_path


def generate_certificate_html(
    user_id: UUID,
    role: str,
    level: str,
    count: int,
    certificate_id: str,
    db: Session,
) -> str:
    user_name = get_user_name(db, user_id)
    date = datetime.now().strftime("%B %d, %Y")

    template_str = DONOR_TEMPLATE if role == "donor" else VOLUNTEER_TEMPLATE
    template = Template(template_str)

    html = template.render(
        user_name=user_name,
        level=level,
        count=count,
        certificate_id=certificate_id,
        date=date,
    )

    return html


def check_and_generate_certificate(
    user_id: UUID,
    role: str,
    db: Session,
    background_tasks=None,
):
    if role not in ("donor", "volunteer"):
        return None

    if role == "donor":
        count = (
            db.query(models.Donation)
            .filter(
                models.Donation.donor_id == user_id,
                models.Donation.status == models.DonationStatusEnum.COMPLETED,
            )
            .count()
        )
    else:
        count = (
            db.query(models.Delivery)
            .filter(
                models.Delivery.volunteer_id == user_id,
                models.Delivery.status == models.DeliveryStatusEnum.DELIVERED,
            )
            .count()
        )

    level = get_level(count)
    if not level:
        logger.debug(
            f"User {user_id} ({role}) has no achievement level yet (count: {count})"
        )
        return None

    existing = (
        db.query(models.Certificate)
        .filter_by(user_id=user_id, role=role, level=level)
        .first()
    )

    if existing:
        logger.debug(
            f"Certificate already exists for user {user_id} ({role}) level {level}"
        )
        return existing

    certificate_id = (
        f"FB-{role[:3].upper()}-{datetime.now().year}-{str(user_id)[:8]}-{count}"
    )
    certificate_id = certificate_id.upper()

    cert_path = generate_certificate_pdf(
        user_id, role, level, count, certificate_id, db
    )

    new_cert = models.Certificate(
        user_id=user_id,
        role=role,
        level=level,
        total_count=count,
        certificate_id=certificate_id,
        certificate_url=cert_path,
    )

    db.add(new_cert)
    db.commit()
    db.refresh(new_cert)

    logger.info(f"Certificate generated for user {user_id} ({role}) level {level}")

    if background_tasks:
        from app.services.email_service import send_certificate_email

        background_tasks.add_task(
            send_certificate_email, user_id, cert_path, level, role
        )

    return new_cert


def get_user_certificates(db: Session, user_id: UUID):
    return (
        db.query(models.Certificate).filter(models.Certificate.user_id == user_id).all()
    )


def get_user_achievement(db: Session, user_id: UUID, role: str):
    if role == "donor":
        count = (
            db.query(models.Donation)
            .filter(
                models.Donation.donor_id == user_id,
                models.Donation.status == models.DonationStatusEnum.COMPLETED,
            )
            .count()
        )
    elif role == "volunteer":
        count = (
            db.query(models.Delivery)
            .filter(
                models.Delivery.volunteer_id == user_id,
                models.Delivery.status == models.DeliveryStatusEnum.DELIVERED,
            )
            .count()
        )
    else:
        count = 0

    level = get_level(count)
    next_info = get_next_level(count)

    return {
        "role": role,
        "current_level": level,
        "next_level": next_info[1] if next_info else None,
        "total_completed": count,
        "remaining": next_info[0] - count if next_info else 0,
    }

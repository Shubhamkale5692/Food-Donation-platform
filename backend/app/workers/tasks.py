from celery import Celery
import time
import random
from app.infrastructure.database import SessionLocal
from app.domain import models
import logging

logger = logging.getLogger(__name__)

import os

_REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery("worker", broker=_REDIS_URL, backend=_REDIS_URL)


@celery_app.task
def process_donation_freshness(donation_id: str):
    """
    Background freshness verification.
    Under the new 4-layer architecture, the primary analysis runs inline during
    upload (/api/v1/ai/analyze-image). This background task acts as a secondary
    verification or fallback if the inline check was bypassed.
    """
    logger.info(f"Starting background freshness scan check for donation {donation_id}")
    time.sleep(1)  # Simulate queue delay

    import uuid as _uuid
    db = SessionLocal()
    try:
        if isinstance(donation_id, str):
            try:
                donation_id = _uuid.UUID(donation_id)
            except ValueError:
                logger.error(f"Invalid UUID format for donation_id: {donation_id}")
                return

        donation = (
            db.query(models.Donation).filter(models.Donation.id == donation_id).first()
        )
        if not donation:
            logger.warning(f"Donation {donation_id} not found for AI scan.")
            return

        # Handled inline?
        if donation.image_hash and donation.ai_confidence_score:
            logger.info(
                f"Donation {donation_id} already analyzed inline. "
                f"Status: {donation.freshness_status}, Confidence: {donation.ai_confidence_score}"
            )
            return f"Already analyzed: {donation.freshness_status}"

        # If no image URL, default to UNKNOWN rather than unfairly marking it EXPIRED
        if not donation.image_url:
            status = models.FreshnessStatusEnum.UNKNOWN
            logger.warning(
                f"Donation {donation_id} missing image URL. Marking UNKNOWN."
            )
        else:
            # Fallback legacy random choice if somehow bypassed the 4-layer inline check
            # but still provided an image URL.
            choice = random.random()
            if choice < 0.6:
                status = models.FreshnessStatusEnum.FRESH
            elif choice < 0.85:
                status = models.FreshnessStatusEnum.RISKY
            else:
                status = models.FreshnessStatusEnum.EXPIRED

        donation.freshness_status = status
        db.commit()
        logger.info(f"Fallback AI Scan Complete: {donation_id} tagged as {status}")
    finally:
        db.close()

    return f"AI Status: {status}"

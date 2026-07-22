import enum
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Integer,
    Float,
    ForeignKey,
    Enum,
    UUID,
    Text,
)
from sqlalchemy.orm import relationship
from app.infrastructure.database import Base
import uuid
from datetime import datetime, timezone, timedelta


def _utcnow():
    from datetime import timezone

    return datetime.now(timezone.utc)


class RoleEnum(str, enum.Enum):
    ADMIN = "Admin"
    NGO = "NGO"
    DONOR = "Donor"
    VOLUNTEER = "Volunteer"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # For NGO approval
    trust_score = Column(Integer, default=100)  # For fraud detection
    created_at = Column(DateTime, default=_utcnow)

    # For Volunteers
    ngo_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    volunteer_status = Column(String, default="pending")  # pending, approved, rejected

    # New volunteer metrics based on requirements
    status = Column(String, default="pending")  # Alias for volunteer_status
    availability = Column(String, default="available")  # available, busy
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    rating = Column(Float, default=5.0)
    completed_deliveries = Column(Integer, default=0)

    profile = relationship(
        "Profile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    donations = relationship(
        "Donation", back_populates="donor", foreign_keys="[Donation.donor_id]"
    )
    ngo_donations = relationship(
        "Donation", back_populates="ngo", foreign_keys="[Donation.ngo_id]"
    )


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    # Live tracking
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    certificate_url = Column(String, nullable=True)  # For NGOs

    user = relationship("User", back_populates="profile")


class VolunteerLocation(Base):
    __tablename__ = "volunteer_locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    volunteer_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=_utcnow)

    volunteer = relationship("User")


class DonationStatusEnum(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    READY_FOR_DISTRIBUTION = "ready_for_distribution"
    ASSIGNED = "assigned"
    CLAIMED = "claimed"
    PICKED_UP = "picked_up"
    IN_PROGRESS = "in_progress"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISTRIBUTED = "distributed"


class FreshnessStatusEnum(str, enum.Enum):
    UNKNOWN = "Unknown"
    FRESH = "Fresh"
    MEDIUM = "Medium"
    SPOILED = "Spoiled"
    # Legacy DB values (older migrations/data wrote uppercase/lowercase strings).
    # Keep these to prevent ORM LookupError on read.
    UNKNOWN_LEGACY_UPPER = "UNKNOWN"
    UNKNOWN_LEGACY_LOWER = "unknown"
    FRESH_LEGACY_UPPER = "FRESH"
    FRESH_LEGACY_LOWER = "fresh"
    MEDIUM_LEGACY_UPPER = "MEDIUM"
    MEDIUM_LEGACY_LOWER = "medium"
    SPOILED_LEGACY_UPPER = "SPOILED"
    SPOILED_LEGACY_LOWER = "spoiled"
    # Old values for backwards compatibility
    RISKY = "Risky"
    RISKY_LEGACY_UPPER = "RISKY"
    RISKY_LEGACY_LOWER = "risky"
    EXPIRED = "Expired"
    EXPIRED_LEGACY_UPPER = "EXPIRED"
    EXPIRED_LEGACY_LOWER = "expired"


class Donation(Base):
    __tablename__ = "donations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    donor_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    food_type = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    expiry_time = Column(DateTime, nullable=False)
    status = Column(
        Enum(
            DonationStatusEnum,
            values_callable=lambda x: [e.value for e in x],
            native_enum=True,
        ),
        default=DonationStatusEnum.PENDING,
        index=True,
    )
    freshness_status = Column(
        Enum(
            FreshnessStatusEnum,
            values_callable=lambda x: [e.value for e in x],
            native_enum=True,
        ),
        default=FreshnessStatusEnum.UNKNOWN,
    )  # AI Tag
    image_url = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    pickup_latitude = Column(Float, nullable=True)
    pickup_longitude = Column(Float, nullable=True)
    pickup_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # Smart Assignment & Delivery Features
    ngo_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=True
    )  # NGO that claimed
    volunteer_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=True
    )
    delivery_status = Column(
        String, default="pending"
    )  # pending, assigned, claimed, picked_up, delivered
    otp_code = Column(String, nullable=True)
    otp_verified = Column(Boolean, default=False)
    otp_generated_at = Column(DateTime, nullable=True)  # For 10-minute OTP expiry
    otp_last_sent_at = Column(DateTime, nullable=True)  # Cooldown between regenerations
    pickup_time = Column(DateTime, nullable=True)
    delivery_time = Column(DateTime, nullable=True)
    volunteer_reached_donor = Column(
        Boolean, default=False
    )  # Volunteer reached donor location
    donation_received = Column(
        Boolean, default=False
    )  # Volunteer received donation from donor
    assignment_time = Column(DateTime, nullable=True)  # When volunteer was assigned
    pickup_location = Column(
        String, nullable=True
    )  # Alias for human-readable pickup address
    cancel_reason = Column(String, nullable=True)  # Reason provided by donor on cancel

    # Safe improvements
    category = Column(String, nullable=True)  # e.g., "General", "Packaged", "Cooked"
    is_deleted = Column(Boolean, default=False)  # Soft delete flag
    task_type = Column(String(20), default="pickup")  # pickup, distribution
    distribution_status = Column(String(20), default="pending")  # pending, in_progress, completed
    distribution_otp = Column(String(10), nullable=True)

    # Delivery Timer Tracking
    start_time = Column(DateTime, nullable=True)  # When donation was created
    total_duration = Column(Integer, nullable=True)  # Total delivery time in minutes

    # Food Testing & Decision System
    food_quality = Column(String, nullable=True)  # fresh, moderate, spoiled
    decision = Column(String, nullable=True)  # distribute, urgent, rejected
    tested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tested_at = Column(DateTime, nullable=True)
    remarks = Column(String, nullable=True)

    donor = relationship("User", back_populates="donations", foreign_keys=[donor_id])
    ngo = relationship(
        "User", foreign_keys="[Donation.ngo_id]", back_populates="ngo_donations"
    )
    delivery = relationship("Delivery", back_populates="donation", uselist=False)
    beneficiary = relationship("Beneficiary", back_populates="donations")

    # ── AI Freshness Analysis fields (added for 4-layer upgrade) ────────────
    ai_confidence_score = Column(
        Float, nullable=True
    )  # CNN prediction confidence 0.0–1.0
    image_timestamp = Column(DateTime, nullable=True)  # EXIF capture timestamp
    image_hash = Column(String(64), nullable=True)  # MD5 hex – duplicate detection
    image_source = Column(String(16), nullable=True)  # 'camera' or 'upload'

    # ── Lifecycle Tracking Timestamps (industry-level delivery tracking) ─────
    donation_posted_at = Column(DateTime, nullable=True)  # When donation was posted
    pickup_accepted_at = Column(DateTime, nullable=True)  # When NGO accepted
    picked_up_at = Column(DateTime, nullable=True)  # When volunteer picked up
    delivered_at = Column(DateTime, nullable=True)  # When volunteer delivered
    received_at = Column(DateTime, nullable=True)  # When NGO confirmed receipt

    # ── Beneficiary Module Fields (non-breaking, all nullable) ─────────────────────
    beneficiary_id = Column(
        UUID(as_uuid=True), ForeignKey("beneficiaries.id", ondelete="SET NULL"), nullable=True
    )
    delivery_partner_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    receiver_name = Column(String(255), nullable=True)


class DeliveryStatusEnum(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    FAILED = "failed"


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    donation_id = Column(
        UUID(as_uuid=True), ForeignKey("donations.id"), unique=True, nullable=False
    )
    ngo_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    volunteer_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=True
    )
    status = Column(
        Enum(DeliveryStatusEnum), default=DeliveryStatusEnum.PENDING, index=True
    )
    otp = Column(String, nullable=True)  # For pickup confirmation
    assigned_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    donation = relationship("Donation", back_populates="delivery")
    ngo = relationship("User", foreign_keys=[ngo_id])
    volunteer = relationship("User", foreign_keys=[volunteer_id])


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    message = Column(String, nullable=False)
    notification_type = Column(
        String, default="info"
    )  # info, assignment, completion, alert
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User")


class LocationTracking(Base):
    __tablename__ = "location_tracking"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    volunteer_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    donation_id = Column(
        UUID(as_uuid=True), ForeignKey("donations.id"), index=True, nullable=True
    )
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=_utcnow)

    volunteer = relationship("User", foreign_keys=[volunteer_id])
    donation = relationship("Donation")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    sender_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    receiver_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    donation_id = Column(
        UUID(as_uuid=True), ForeignKey("donations.id"), index=True, nullable=False
    )
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=_utcnow)
    is_read = Column(Boolean, default=False)
    status = Column(String, default="sent")  # sent, delivered, seen
    delivered_at = Column(DateTime, nullable=True)
    seen_at = Column(DateTime, nullable=True)

    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])
    donation = relationship("Donation")


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    role = Column(String(20), nullable=False)  # donor, volunteer
    level = Column(String(20), nullable=False)  # Bronze, Silver, Gold, Platinum
    total_count = Column(Integer, nullable=False)
    certificate_id = Column(String(50), unique=True, nullable=False)
    issued_at = Column(DateTime, default=_utcnow)
    certificate_url = Column(String, nullable=True)
    email_sent = Column(Boolean, default=False)

    user = relationship("User", foreign_keys=[user_id])


class BeneficiaryType(str, enum.Enum):
    NGO = "NGO"
    SHELTER = "Shelter"
    INDIVIDUAL = "Individual"


class Beneficiary(Base):
    """Beneficiary / Recipient table for delivery completion."""

    __tablename__ = "beneficiaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False)
    type = Column(Enum(BeneficiaryType), nullable=False)
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    contact_number = Column(String(20), nullable=True)
    capacity = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    is_active = Column(Boolean, default=True)

    donations = relationship("Donation", back_populates="beneficiary")


class DonationEvent(Base):
    """Audit log for donation lifecycle state transitions."""

    __tablename__ = "donation_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    donation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("donations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action = Column(
        String(50), nullable=False
    )  # CREATED, ACCEPTED, PICKED_UP, DELIVERED, RECEIVED, CANCELLED
    performed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False)

    donation = relationship("Donation")
    user = relationship("User", foreign_keys=[performed_by])

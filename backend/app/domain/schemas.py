import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from app.domain.models import (
    RoleEnum,
    DonationStatusEnum,
    FreshnessStatusEnum,
    DeliveryStatusEnum,
    BeneficiaryType,
)
from typing import Any


# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    role: RoleEnum


class UserCreate(UserBase):
    password: str
    name: str
    ngo_id: Optional[uuid.UUID] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        # BUG-7 Fix: was 6, now matches security.py MIN_PASSWORD_LENGTH = 8
        from app.core.security import MIN_PASSWORD_LENGTH

        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
            )
        return v


class UserResponse(UserBase):
    id: uuid.UUID
    name: Optional[str] = None
    is_active: bool
    is_verified: bool
    trust_score: int
    created_at: datetime
    ngo_id: Optional[uuid.UUID] = None
    volunteer_status: Optional[str] = None
    status: Optional[str] = None
    availability: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    rating: Optional[float] = None
    completed_deliveries: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class FraudAlertResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    trust_score: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TopVolunteer(BaseModel):
    name: str
    deliveries: int


class ImpactAnalyticsResponse(BaseModel):
    total_waste_reduced_kg: float
    total_meals_served: int
    top_volunteers: list[TopVolunteer]

    model_config = ConfigDict(from_attributes=True)


# --- Profile Schemas ---
class ProfileBase(BaseModel):
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    certificate_url: Optional[str] = None


class ProfileResponse(ProfileBase):
    id: uuid.UUID
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


# --- Auth Schemas ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenUser(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr


class Token(BaseModel):
    access_token: str
    token: Optional[str] = Field(default=None)
    token_type: str
    role: str
    success: bool = True
    user: Optional[TokenUser] = None


class TokenData(BaseModel):
    sub: Optional[str] = None


# --- Donation Schemas ---
class DonationBase(BaseModel):
    food_type: str
    quantity: int = Field(gt=0, description="Quantity must be positive")
    expiry_time: datetime
    latitude: Optional[float] = Field(
        None, ge=-90, le=90, description="Latitude must be between -90 and 90"
    )
    longitude: Optional[float] = Field(
        None, ge=-180, le=180, description="Longitude must be between -180 and 180"
    )
    pickup_latitude: Optional[float] = Field(None, ge=-90, le=90)
    pickup_longitude: Optional[float] = Field(None, ge=-180, le=180)
    pickup_address: Optional[str] = None
    image_url: Optional[str] = None


class DonationCreate(DonationBase):
    freshness_status: Optional[FreshnessStatusEnum] = None
    ai_confidence_score: Optional[float] = None
    image_hash: Optional[str] = None
    image_source: Optional[str] = None
    image_timestamp: Optional[datetime] = None

    @field_validator("expiry_time", mode="after")
    @classmethod
    def expiry_must_be_future(cls, v: datetime) -> datetime:
        """Bug 2 Fix: Enforce future expiry time only on new donation creation."""
        aware_v = v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v
        if aware_v <= datetime.now(timezone.utc):
            raise ValueError("Expiry time must be in the future")
        return v


class DonationResponse(DonationBase):
    id: uuid.UUID
    donor_id: uuid.UUID
    status: DonationStatusEnum
    freshness_status: FreshnessStatusEnum
    pickup_latitude: Optional[float] = None
    pickup_longitude: Optional[float] = None
    pickup_address: Optional[str] = None
    is_recommended: Optional[bool] = False
    ai_confidence_score: Optional[float] = None
    image_hash: Optional[str] = None
    image_source: Optional[str] = None
    image_timestamp: Optional[datetime] = None
    created_at: datetime

    ngo_id: Optional[uuid.UUID] = None
    ngo_name: Optional[str] = None
    volunteer_id: Optional[uuid.UUID] = None
    volunteer_name: Optional[str] = None
    volunteer_phone: Optional[str] = None
    delivery_status: Optional[str] = None
    otp_code: Optional[str] = None
    otp_verified: Optional[bool] = None
    otp_generated_at: Optional[datetime] = None
    otp_expires_at: Optional[datetime] = None
    otp_seconds_remaining: Optional[int] = None
    otp_validity_seconds: Optional[int] = None
    otp_resend_available_in_seconds: Optional[int] = None
    otp_regenerate_cooldown_seconds: Optional[int] = None
    volunteer_reached_donor: Optional[bool] = None
    donation_received: Optional[bool] = None
    pickup_time: Optional[datetime] = None
    delivery_time: Optional[datetime] = None
    assignment_time: Optional[datetime] = None
    pickup_location: Optional[str] = None
    cancel_reason: Optional[str] = None
    start_time: Optional[datetime] = None
    total_duration: Optional[int] = None
    food_quality: Optional[str] = None
    decision: Optional[str] = None
    tested_at: Optional[datetime] = None
    remarks: Optional[str] = None
    task_type: Optional[str] = None
    distribution_status: Optional[str] = None
    distribution_otp: Optional[str] = None

    # Lifecycle tracking timestamps
    donation_posted_at: Optional[datetime] = None
    pickup_accepted_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    received_at: Optional[datetime] = None

    # Computed lifecycle fields (not stored in DB)
    lifecycle_status: Optional[str] = None
    lifecycle_timestamps: Optional[dict[str, Any]] = None
    lifecycle_durations: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# --- Delivery Schemas ---
class DeliveryCreate(BaseModel):
    ngo_id: uuid.UUID
    volunteer_id: uuid.UUID
    donation_id: uuid.UUID


class DeliveryResponse(BaseModel):
    id: uuid.UUID
    donation_id: uuid.UUID
    ngo_id: uuid.UUID
    volunteer_id: uuid.UUID
    status: DeliveryStatusEnum
    otp: Optional[str] = None
    assigned_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OTPVerify(BaseModel):
    otp: str


class LocationUpdate(BaseModel):
    latitude: float
    longitude: float


class VolunteerLocationUpdate(BaseModel):
    volunteer_id: Optional[uuid.UUID] = None
    latitude: float
    longitude: float
    timestamp: Optional[str] = None


class LocationTrackingCreate(BaseModel):
    donation_id: Optional[uuid.UUID] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class LocationTrackingResponse(BaseModel):
    id: uuid.UUID
    volunteer_id: uuid.UUID
    donation_id: Optional[uuid.UUID]
    latitude: float
    longitude: float
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class MarkPickedUpRequest(BaseModel):
    donation_id: uuid.UUID
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class LocationBroadcastMessage(BaseModel):
    type: str = "LOCATION_UPDATE"
    donation_id: uuid.UUID
    volunteer_id: uuid.UUID
    latitude: float
    longitude: float
    timestamp: datetime
    status: str


# --- Status Update Schema (for PUT /donations/{id}/status) ---
class DonationStatusUpdate(BaseModel):
    status: DonationStatusEnum


class CancelDonationRequest(BaseModel):
    """Body for POST /donations/cancel/{id}"""

    cancel_reason: Optional[str] = None


class DonationLocationPayload(BaseModel):
    latitude: float
    longitude: float
    full_address: str


# --- Admin Dashboard Schemas ---
class AdminSystemUserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str
    join_date: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class AdminSystemDonationResponse(BaseModel):
    id: uuid.UUID
    donor_name: str
    food_type: str
    quantity: int
    pickup_location: str
    assigned_volunteer: Optional[str] = None
    delivery_status: str

    model_config = ConfigDict(from_attributes=True)


class AdminActivityTimelineResponse(BaseModel):
    id: uuid.UUID
    activity_type: str
    message: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class ChartDataset(BaseModel):
    label: str
    data: list[int | float]


class AdminAnalyticsChartsResponse(BaseModel):
    monthly_donations: dict[str, list]
    ngo_performance: dict[str, list]
    volunteer_stats: dict[str, list]


# --- AI Schemas ---
class AiVolunteerAssignmentRequest(BaseModel):
    donation_id: uuid.UUID


class AiVolunteerAssignmentResponse(BaseModel):
    best_volunteer_id: Optional[uuid.UUID] = None
    volunteer_id: Optional[uuid.UUID] = None
    confidence_score: float
    confidence: Optional[float] = None
    volunteer_name: str
    name: Optional[str] = None
    distance_km: Optional[float] = None
    distance: Optional[float] = None
    reason: Optional[str] = None


class AiFreshnessRequest(BaseModel):
    image_url: str


class AiFreshnessResponse(BaseModel):
    freshness_status: str
    confidence_score: float


class AiHeatmapPoint(BaseModel):
    lat: float
    lng: float
    weight: float


class AiFraudCheckRequest(BaseModel):
    user_id: uuid.UUID


class AiFraudCheckResponse(BaseModel):
    user_id: uuid.UUID
    fraud_risk_score: float
    is_flagged: bool
    reason: str


class AiRecommendationsResponse(BaseModel):
    recommended_ngo: str
    best_pickup_time: str
    suggested_food_items: list[str]


class AiImpactInsightsResponse(BaseModel):
    insights: list[str]
    generated_at: str


# --- Message Schemas ---
class MessageCreate(BaseModel):
    receiver_id: uuid.UUID
    donation_id: uuid.UUID
    message: str = Field(..., min_length=1, max_length=2000)


class MessageResponse(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    receiver_id: uuid.UUID
    donation_id: uuid.UUID
    message: str
    timestamp: datetime
    is_read: bool
    status: Optional[str] = "sent"
    delivered_at: Optional[datetime] = None
    seen_at: Optional[datetime] = None

    sender_name: Optional[str] = None
    receiver_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SendMessageRequest(BaseModel):
    receiver_id: uuid.UUID
    donation_id: uuid.UUID
    message: str = Field(..., min_length=1, max_length=2000)


class MarkReadRequest(BaseModel):
    donation_id: uuid.UUID


class MarkSeenRequest(BaseModel):
    donation_id: uuid.UUID
    message_ids: Optional[list[uuid.UUID]] = None


class EmergencyAlertRequest(BaseModel):
    donation_id: uuid.UUID
    message: Optional[str] = "Emergency! Need help immediately!"


# ── AI Image Analysis (4-Layer freshness verification) ────────────────────────
class AiImageAnalysisResponse(BaseModel):
    """Full 4-layer AI freshness analysis result returned to the donor frontend."""

    freshness_status: str  # Fresh | Medium | Spoiled
    confidence_score: float  # 0.0 – 1.0
    food_type: str  # "cooked" | "raw" | "packaged"
    recommendation: str  # Smart recommendation based on freshness
    probabilities: dict  # {"Fresh": 0.72, "Medium": 0.20, "Spoiled": 0.08}
    image_source: str  # 'camera' | 'upload'
    image_timestamp: Optional[str] = None
    image_hash: str  # MD5 hex for duplicate tracking
    warnings: list[str]  # Human-readable warning messages
    duplicate_warning: Optional[str] = None
    layers_checked: list[str]  # Summary of which layers ran


# ── Donation Event (Audit Log) ─────────────────────────────────────────────
class DonationEventResponse(BaseModel):
    id: uuid.UUID
    donation_id: uuid.UUID
    action: str
    performed_by: Optional[uuid.UUID] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class DonationLifecycleResponse(BaseModel):
    donation_id: uuid.UUID
    lifecycle_status: str
    timestamps: dict[str, Any]
    durations: dict[str, Any]
    events: list[DonationEventResponse]

    model_config = ConfigDict(from_attributes=True)


# ── Beneficiary Schemas ────────────────────────────────────────────────────────
class BeneficiaryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: BeneficiaryType
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    contact_number: Optional[str] = Field(None, max_length=20)
    capacity: Optional[int] = Field(None, ge=0)


class BeneficiaryCreate(BeneficiaryBase):
    pass


class BeneficiaryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[BeneficiaryType] = None
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    contact_number: Optional[str] = Field(None, max_length=20)
    capacity: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class BeneficiaryResponse(BeneficiaryBase):
    id: uuid.UUID
    created_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ── Delivery Completion Schemas ────────────────────────────────────────────────
class DeliveryCompletionRequest(BaseModel):
    """Request body for completing a delivery."""

    receiver_name: Optional[str] = Field(None, max_length=255)
    otp_verified: Optional[bool] = False


class DeliveryCompletionResponse(BaseModel):
    """Response after delivery completion."""

    donation_id: uuid.UUID
    status: str
    delivered_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    receiver_name: Optional[str] = None
    beneficiary_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AssignBeneficiaryRequest(BaseModel):
    """Request to assign a beneficiary to a donation."""

    beneficiary_id: uuid.UUID
    delivery_partner_id: Optional[uuid.UUID] = None

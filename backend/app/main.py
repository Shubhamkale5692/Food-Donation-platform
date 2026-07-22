import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.interfaces import (
    auth_router,
    donation_router,
    admin_router,
    volunteer_router,
    ai_router,
    stats_router,
    ngo_router,
    beneficiary_router,
)
from app.interfaces.certificate_router import router as certificate_router
from app.infrastructure.database import engine
from app.domain import models
from fastapi import WebSocket, WebSocketDisconnect


from app.services import websocket_service

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Execute ORM table creation
    models.Base.metadata.create_all(bind=engine)

    _applied = 0
    _skipped = 0
    for _label, _ddl in _COLUMN_MIGRATIONS + _ENUM_MIGRATIONS + _DATA_MIGRATIONS:
        try:
            with engine.begin() as _conn:
                _conn.execute(_sql(_ddl))
            _applied += 1
            logger.debug("Migration OK  : %s", _label)
        except Exception as _exc:
            _skipped += 1
            logger.warning("Migration SKIP: %s — %s", _label, _exc)

    logger.info(
        "Auto-migrations complete: %d applied, %d skipped (already exist or not applicable).",
        _applied,
        _skipped,
    )
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="FoodBridge Core API – connecting surplus food to those in need.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Explicit origin list required for credentialed requests (Authorization header).
# "allow_origins=['*']" with "allow_credentials=True" is rejected by browsers.
#
# Origins covered:
#   - http://localhost:8080  → Docker: Nginx serves frontend on :8080
#   - http://localhost:80    → Docker: Nginx on standard port
#   - http://localhost:5500  → VS Code / Live Server local dev
#   - http://localhost:3000  → Alternative local dev port
#   - http://127.0.0.1:*    → Same as localhost variants
#   - http://localhost:8000  → Direct backend access during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:80",
        "http://localhost",
        "http://localhost:5500",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Database – auto-create tables (ORM-managed) ───────────────────────────────
# This also creates the `notifications` table via the Notification ORM model.
# NOTE: Execution moved to FastAPI lifespan handler.

# ── Safe Auto-Migrations ───────────────────────────────────────────────────────
# Each statement runs in its own transaction.
# A failure (e.g. column already exists, FK constraint not yet satisfied)
# is logged as a WARNING and skipped — it never blocks subsequent migrations.
# This fixes the critical bug where a single failure prevented `users.ngo_id`
# from being added, causing "column users.ngo_id does not exist" login crashes.
from sqlalchemy import text as _sql

_COLUMN_MIGRATIONS = [
    # ── users table ───────────────────────────────────────────────────────────
    ("users.name", "ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR;"),
    (
        "users.status",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'pending';",
    ),
    (
        "users.location_lat",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lat FLOAT;",
    ),
    (
        "users.location_lng",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lng FLOAT;",
    ),
    (
        "users.rating",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS rating FLOAT DEFAULT 5.0;",
    ),
    (
        "users.completed_deliveries",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS completed_deliveries INTEGER DEFAULT 0;",
    ),
    (
        "users.volunteer_status",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS volunteer_status VARCHAR DEFAULT 'pending';",
    ),
    (
        "users.availability",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS availability VARCHAR DEFAULT 'available';",
    ),
    # CRITICAL: ngo_id must run after users table exists (self-referential FK).
    # Previously this was inside a monolithic try-block and could be skipped if
    # any earlier statement raised an exception → caused login crashes.
    # Using nullable column without FK constraint for compatibility
    (
        "users.ngo_id",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS ngo_id UUID;",
    ),
    # ── donations table ───────────────────────────────────────────────────────
    (
        "donations.volunteer_id",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS volunteer_id UUID REFERENCES users(id);",
    ),
    (
        "donations.delivery_status",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_status VARCHAR DEFAULT 'pending';",
    ),
    (
        "donations.otp_code",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_code VARCHAR;",
    ),
    (
        "donations.otp_verified",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_verified BOOLEAN DEFAULT FALSE;",
    ),
    (
        "donations.pickup_time",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_time TIMESTAMP;",
    ),
    (
        "donations.delivery_time",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_time TIMESTAMP;",
    ),
    (
        "donations.start_time",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS start_time TIMESTAMP;",
    ),
    (
        "donations.total_duration",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS total_duration INTEGER;",
    ),
    (
        "donations.ai_confidence_score",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS ai_confidence_score FLOAT;",
    ),
    (
        "donations.assignment_time",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS assignment_time TIMESTAMP;",
    ),
    (
        "donations.pickup_location",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_location VARCHAR;",
    ),
    (
        "donations.cancel_reason",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS cancel_reason VARCHAR;",
    ),
    (
        "donations.otp_generated_at",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_generated_at TIMESTAMP;",
    ),
    (
        "donations.otp_last_sent_at",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_last_sent_at TIMESTAMP;",
    ),
    (
        "donations.volunteer_reached_donor",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS volunteer_reached_donor BOOLEAN DEFAULT FALSE;",
    ),
    (
        "donations.donation_received",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS donation_received BOOLEAN DEFAULT FALSE;",
    ),
    (
        "donations.category",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS category VARCHAR;",
    ),
    (
        "donations.is_deleted",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;",
    ),
    # ── Food Testing & Decision System columns ────────────────────────────
    (
        "donations.food_quality",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS food_quality VARCHAR(20);",
    ),
    (
        "donations.decision",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS decision VARCHAR(20);",
    ),
    (
        "donations.tested_by",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS tested_by TEXT;",
    ),
    (
        "donations.tested_at",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS tested_at TIMESTAMP;",
    ),
    (
        "donations.remarks",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS remarks TEXT;",
    ),
    (
        "donations.idx_decision",
        "CREATE INDEX IF NOT EXISTS idx_donations_decision ON donations(decision);",
    ),
    # ── indexes ───────────────────────────────────────────────────────────────
    # NOTE: idx_notifications_user_id is NOT listed here.
    # The Notification ORM model has index=True on user_id so SQLAlchemy
    # creates it automatically via Base.metadata.create_all above.
    (
        "idx.donations_volunteer_id",
        "CREATE INDEX IF NOT EXISTS idx_donations_volunteer_id ON donations(volunteer_id);",
    ),
    # ── deliveries table ───────────────────────────────────────────────────
    (
        "deliveries.create",
        """CREATE TABLE IF NOT EXISTS deliveries (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        donation_id UUID NOT NULL REFERENCES donations(id) UNIQUE,
        ngo_id UUID NOT NULL REFERENCES users(id),
        volunteer_id UUID,
        status VARCHAR(50) DEFAULT 'pending',
        otp VARCHAR,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",
    ),
    (
        "deliveries.volunteer_id_nullable",
        """ALTER TABLE deliveries ALTER COLUMN volunteer_id DROP NOT NULL;""",
    ),
    # ── location_tracking table ──────────────────────────────────────────────
    (
        "location_tracking.create",
        """CREATE TABLE IF NOT EXISTS location_tracking (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        volunteer_id UUID NOT NULL REFERENCES users(id),
        donation_id UUID REFERENCES donations(id),
        latitude FLOAT NOT NULL,
        longitude FLOAT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",
    ),
    (
        "location_tracking.idx_donation_id",
        "CREATE INDEX IF NOT EXISTS idx_location_tracking_donation_id ON location_tracking(donation_id);",
    ),
    (
        "location_tracking.idx_volunteer_id",
        "CREATE INDEX IF NOT EXISTS idx_location_tracking_volunteer_id ON location_tracking(volunteer_id);",
    ),
    # ── donations table location columns ─────────────────────────────────────
    (
        "donations.pickup_latitude",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_latitude FLOAT;",
    ),
    (
        "donations.pickup_longitude",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_longitude FLOAT;",
    ),
    # ── messages table ────────────────────────────────────────────────────────
    (
        "messages.create",
        """CREATE TABLE IF NOT EXISTS messages (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        sender_id UUID NOT NULL REFERENCES users(id),
        receiver_id UUID NOT NULL REFERENCES users(id),
        donation_id UUID NOT NULL REFERENCES donations(id),
        message TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_read BOOLEAN DEFAULT FALSE
    );""",
    ),
    (
        "messages.idx_donation_id",
        "CREATE INDEX IF NOT EXISTS idx_messages_donation_id ON messages(donation_id);",
    ),
    (
        "messages.idx_sender_id",
        "CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id);",
    ),
    (
        "messages.idx_receiver_id",
        "CREATE INDEX IF NOT EXISTS idx_messages_receiver_id ON messages(receiver_id);",
    ),
]

# Enum-safety fixes: convert native PostgreSQL ENUM columns to VARCHAR so the
# ORM can write both legacy uppercase and current lowercase enum values.
_ENUM_MIGRATIONS = [
    (
        "enum.donations.status",
        """DO $$ BEGIN
        IF (SELECT data_type FROM information_schema.columns
            WHERE table_name='donations' AND column_name='status') != 'character varying' THEN
            ALTER TABLE donations ALTER COLUMN status DROP DEFAULT;
            ALTER TABLE donations ALTER COLUMN status TYPE VARCHAR(50) USING CAST(status AS VARCHAR(50));
            ALTER TABLE donations ALTER COLUMN status SET DEFAULT 'pending';
        END IF;
    END $$;""",
    ),
    (
        "enum.donations.freshness_status",
        """DO $$ BEGIN
        IF (SELECT data_type FROM information_schema.columns
            WHERE table_name='donations' AND column_name='freshness_status') != 'character varying' THEN
            ALTER TABLE donations ALTER COLUMN freshness_status DROP DEFAULT;
            ALTER TABLE donations ALTER COLUMN freshness_status TYPE VARCHAR(50) USING CAST(freshness_status AS VARCHAR(50));
            ALTER TABLE donations ALTER COLUMN freshness_status SET DEFAULT 'Unknown';
        END IF;
    END $$;""",
    ),
    (
        "enum.deliveries.status",
        """DO $$ BEGIN
        IF (SELECT data_type FROM information_schema.columns
            WHERE table_name='deliveries' AND column_name='status') != 'character varying' THEN
            ALTER TABLE deliveries ALTER COLUMN status DROP DEFAULT;
            ALTER TABLE deliveries ALTER COLUMN status TYPE VARCHAR(50) USING CAST(status AS VARCHAR(50));
            ALTER TABLE deliveries ALTER COLUMN status SET DEFAULT 'Assigned';
        END IF;
    END $$;""",
    ),
]

# Data-sync migrations: backfill values from related columns / profiles.
_DATA_MIGRATIONS = [
    (
        "data.sync_volunteer_status",
        "UPDATE users SET status = volunteer_status WHERE role::text IN ('Volunteer', 'VOLUNTEER') AND volunteer_status IS NOT NULL;",
    ),
    (
        "data.default_availability",
        "UPDATE users SET availability = COALESCE(availability, 'available') WHERE role::text IN ('Volunteer', 'VOLUNTEER');",
    ),
    (
        "data.sync_name_from_profile",
        "UPDATE users u SET name = p.name FROM profiles p WHERE u.id = p.user_id AND (u.name IS NULL OR u.name = '');",
    ),
    (
        "certificates.create",
        """CREATE TABLE IF NOT EXISTS certificates (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id),
        role VARCHAR(20) NOT NULL,
        level VARCHAR(20) NOT NULL,
        total_count INTEGER NOT NULL,
        certificate_id VARCHAR(50) UNIQUE NOT NULL,
        issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        certificate_url TEXT,
        email_sent BOOLEAN DEFAULT FALSE
    );""",
    ),
    (
        "certificates.user_id_idx",
        "CREATE INDEX IF NOT EXISTS idx_certificates_user_id ON certificates(user_id);",
    ),
    # ── Beneficiary Module Migrations (Non-Breaking) ──────────────────────────────
    (
        "beneficiaries.create",
        """CREATE TABLE IF NOT EXISTS beneficiaries (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        type VARCHAR(50) NOT NULL CHECK (type IN ('NGO', 'Shelter', 'Individual')),
        address TEXT,
        latitude FLOAT,
        longitude FLOAT,
        contact_number VARCHAR(20),
        capacity INTEGER,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE
    );""",
    ),
    (
        "beneficiaries.beneficiary_id",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS beneficiary_id UUID REFERENCES beneficiaries(id);",
    ),
    (
        "beneficiaries.delivery_partner_id",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_partner_id UUID REFERENCES users(id);",
    ),
    (
        "beneficiaries.receiver_name",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS receiver_name VARCHAR(255);",
    ),
    (
        "beneficiaries.idx_beneficiary",
        "CREATE INDEX IF NOT EXISTS idx_donations_beneficiary ON donations(beneficiary_id);",
    ),
    (
        "beneficiaries.idx_delivery_partner",
        "CREATE INDEX IF NOT EXISTS idx_donations_delivery_partner ON donations(delivery_partner_id);",
    ),
]

# Safe migrations execution moved to FastAPI lifespan handler.

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(
    auth_router.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["auth"],
)
app.include_router(
    donation_router.router,
    prefix=f"{settings.API_V1_STR}/donations",
    tags=["donations"],
)
app.include_router(
    admin_router.router,
    prefix=f"{settings.API_V1_STR}/admin",
    tags=["admin"],
)
app.include_router(
    volunteer_router.router,
    prefix=f"{settings.API_V1_STR}/volunteer",
    tags=["volunteer"],
)
app.include_router(
    ai_router.router,
    prefix=f"{settings.API_V1_STR}/ai",
    tags=["ai"],
)
app.include_router(
    stats_router.router,
    prefix=f"{settings.API_V1_STR}/stats",
    tags=["stats"],
)
app.include_router(
    ngo_router.router,
    prefix=f"{settings.API_V1_STR}/ngo",
    tags=["ngo"],
)
from app.interfaces.notifications_router import router as notifications_router

app.include_router(
    notifications_router,
    prefix=f"{settings.API_V1_STR}/notifications",
    tags=["notifications"],
)

from app.interfaces.chat_router import router as chat_router

app.include_router(
    chat_router,
    prefix=f"{settings.API_V1_STR}/messages",
    tags=["messages"],
)

app.include_router(
    chat_router,
    prefix=f"{settings.API_V1_STR}/chat",
    tags=["messages_legacy"],
)

from app.interfaces.location_router import router as location_router

app.include_router(
    location_router,
    prefix=f"{settings.API_V1_STR}/tracking",
    tags=["tracking"],
)

from app.interfaces.certificate_router import router as certificate_router

app.include_router(
    certificate_router,
    prefix=f"{settings.API_V1_STR}/user",
    tags=["certificates"],
)

# ── Beneficiary Router ────────────────────────────────────────────────────────────
app.include_router(
    beneficiary_router.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["beneficiaries"],
)

# Alias for root /login as explicitly requested for frontend AngularJS integration
from app.domain import schemas
from app.interfaces.deps import get_db
from sqlalchemy.orm import Session
from fastapi import Depends


@app.post(f"{settings.API_V1_STR}/login", tags=["auth"])
@app.post("/api/login", tags=["auth"])
@app.post("/login", tags=["auth"])
def login_route(credentials: schemas.LoginRequest, db: Session = Depends(get_db)):
    """
    Consolidated login route for ALL entry points (root, /api, and /api/v1).
    """
    from app.interfaces.auth_router import login as auth_login

    return auth_login(credentials=credentials, db=db)


@app.post("/api/logout", tags=["auth"])
@app.post(f"{settings.API_V1_STR}/logout", tags=["auth"])
def api_logout():
    return {"success": True}


@app.post("/signup", response_model=schemas.UserResponse, tags=["auth"])
def root_signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    from app.interfaces.auth_router import register as auth_register

    return auth_register(user_in=user, db=db)


@app.get("/health", tags=["health"])
@limiter.limit("20/minute")
def health_check(request: Request):
    return {"status": "ok", "app": settings.PROJECT_NAME, "version": "1.0.0"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_service.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        await websocket_service.disconnect(websocket)


@app.websocket("/ws/location/{donation_id}")
async def websocket_location_endpoint(websocket: WebSocket, donation_id: str):
    """
    WebSocket endpoint for real-time location tracking.
    Path: /ws/location/{donation_id}
    Query param: ?token=<JWT>
    """
    from app.services import websocket_service as ws

    query_params = websocket.query_params
    token = query_params.get("token", "")

    await ws.handle_location_websocket(websocket, donation_id, token)

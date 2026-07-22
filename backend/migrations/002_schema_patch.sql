-- ============================================================
-- FoodBridge – Emergency DB Schema Patch
-- Run this ONCE against your PostgreSQL database to add
-- all missing columns that the backend ORM expects.
--
-- Usage (Docker):
--   docker exec -i <postgres-container-name> psql -U postgres -d foodbridge < migrations/002_schema_patch.sql
--
-- Usage (local psql):
--   psql -U postgres -d foodbridge -f migrations/002_schema_patch.sql
-- ============================================================

-- ── users table ──────────────────────────────────────────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR;
ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'pending';
ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lat FLOAT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lng FLOAT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS rating FLOAT DEFAULT 5.0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS completed_deliveries INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS volunteer_status VARCHAR DEFAULT 'pending';
ALTER TABLE users ADD COLUMN IF NOT EXISTS availability VARCHAR DEFAULT 'available';

-- CRITICAL: self-referential FK – must run AFTER the users table has its primary key
ALTER TABLE users ADD COLUMN IF NOT EXISTS ngo_id UUID REFERENCES users(id);

-- ── donations table ───────────────────────────────────────────────────────────
ALTER TABLE donations ADD COLUMN IF NOT EXISTS volunteer_id UUID REFERENCES users(id);
ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_status VARCHAR DEFAULT 'pending';
ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_code VARCHAR;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_time TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_time TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS ai_confidence_score FLOAT;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS assignment_time TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_location VARCHAR;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS cancel_reason VARCHAR;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_generated_at TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_last_sent_at TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS volunteer_reached_donor BOOLEAN DEFAULT FALSE;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS donation_received BOOLEAN DEFAULT FALSE;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS category VARCHAR;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;

-- ── notifications table (created by ORM, but ensure it exists) ────────────────
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    message VARCHAR NOT NULL,
    notification_type VARCHAR DEFAULT 'info',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_donations_volunteer_id ON donations(volunteer_id);
CREATE INDEX IF NOT EXISTS idx_donations_status ON donations(status);
CREATE INDEX IF NOT EXISTS idx_donations_ngo_id ON donations(ngo_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);

-- ── Enum → VARCHAR safety conversions ────────────────────────────────────────
DO $$ BEGIN
    IF (SELECT data_type FROM information_schema.columns
        WHERE table_name='donations' AND column_name='status') != 'character varying' THEN
        ALTER TABLE donations ALTER COLUMN status DROP DEFAULT;
        ALTER TABLE donations ALTER COLUMN status TYPE VARCHAR(50) USING CAST(status AS VARCHAR(50));
        ALTER TABLE donations ALTER COLUMN status SET DEFAULT 'pending';
    END IF;
END $$;

DO $$ BEGIN
    IF (SELECT data_type FROM information_schema.columns
        WHERE table_name='donations' AND column_name='freshness_status') != 'character varying' THEN
        ALTER TABLE donations ALTER COLUMN freshness_status DROP DEFAULT;
        ALTER TABLE donations ALTER COLUMN freshness_status TYPE VARCHAR(50) USING CAST(freshness_status AS VARCHAR(50));
        ALTER TABLE donations ALTER COLUMN freshness_status SET DEFAULT 'Unknown';
    END IF;
END $$;

DO $$ BEGIN
    IF (SELECT data_type FROM information_schema.columns
        WHERE table_name='deliveries' AND column_name='status') != 'character varying' THEN
        ALTER TABLE deliveries ALTER COLUMN status DROP DEFAULT;
        ALTER TABLE deliveries ALTER COLUMN status TYPE VARCHAR(50) USING CAST(status AS VARCHAR(50));
        ALTER TABLE deliveries ALTER COLUMN status SET DEFAULT 'Assigned';
    END IF;
END $$;

-- ── Data backfill ─────────────────────────────────────────────────────────────
UPDATE users
    SET status = volunteer_status
    WHERE role::text IN ('Volunteer', 'VOLUNTEER')
      AND volunteer_status IS NOT NULL;

UPDATE users
    SET availability = COALESCE(availability, 'available')
    WHERE role::text IN ('Volunteer', 'VOLUNTEER');

UPDATE users u
    SET name = p.name
    FROM profiles p
    WHERE u.id = p.user_id
      AND (u.name IS NULL OR u.name = '');

-- ── Verification ──────────────────────────────────────────────────────────────
SELECT
    column_name,
    data_type,
    column_default
FROM information_schema.columns
WHERE table_name IN ('users', 'donations', 'notifications')
ORDER BY table_name, ordinal_position;

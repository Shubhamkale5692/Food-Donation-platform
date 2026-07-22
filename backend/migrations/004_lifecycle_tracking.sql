-- ============================================================
-- FoodBridge – Donation Lifecycle Tracking Migration
-- Adds lifecycle timestamp columns and audit log table.
--
-- Usage (Docker):
--   docker exec -i <postgres-container-name> psql -U postgres -d foodbridge < migrations/004_lifecycle_tracking.sql
--
-- Usage (local psql):
--   psql -U postgres -d foodbridge -f migrations/004_lifecycle_tracking.sql
-- ============================================================

-- ── 1. Donation Events audit log table ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS donation_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    donation_id UUID NOT NULL REFERENCES donations(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    performed_by UUID REFERENCES users(id),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_donation_events_donation_id ON donation_events(donation_id);
CREATE INDEX IF NOT EXISTS idx_donation_events_timestamp ON donation_events(timestamp);

-- ── 2. Lifecycle timestamp columns on donations (all nullable) ────────────────
ALTER TABLE donations ADD COLUMN IF NOT EXISTS donation_posted_at TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_accepted_at TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS picked_up_at TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS received_at TIMESTAMP;

-- ── 3. Indexes for lifecycle queries ──────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_donations_donation_posted_at ON donations(donation_posted_at);
CREATE INDEX IF NOT EXISTS idx_donations_delivered_at ON donations(delivered_at);

-- ── 4. Backfill existing rows from legacy columns ─────────────────────────────
UPDATE donations SET donation_posted_at = created_at
    WHERE donation_posted_at IS NULL AND created_at IS NOT NULL;

UPDATE donations SET pickup_accepted_at = assignment_time
    WHERE pickup_accepted_at IS NULL AND assignment_time IS NOT NULL;

UPDATE donations SET picked_up_at = pickup_time
    WHERE picked_up_at IS NULL AND pickup_time IS NOT NULL;

UPDATE donations SET delivered_at = delivery_time
    WHERE delivered_at IS NULL AND delivery_time IS NOT NULL;

-- ── 5. Verification ──────────────────────────────────────────────────────────
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'donations'
  AND column_name IN ('donation_posted_at', 'pickup_accepted_at', 'picked_up_at', 'delivered_at', 'received_at')
ORDER BY column_name;

SELECT
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'donation_events'
ORDER BY ordinal_position;

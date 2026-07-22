-- Full lifecycle migration for FoodBridge donations

-- ── Step 1: Add new enum values ─────────────────────────────
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel='Claimed'    AND enumtypid=(SELECT oid FROM pg_type WHERE typname='donationstatusenum')) THEN
        ALTER TYPE donationstatusenum ADD VALUE 'Claimed'    AFTER 'Assigned';
    END IF;
END; $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel='Picked_Up'  AND enumtypid=(SELECT oid FROM pg_type WHERE typname='donationstatusenum')) THEN
        ALTER TYPE donationstatusenum ADD VALUE 'Picked_Up'  AFTER 'Claimed';
    END IF;
END; $$;

-- ── Step 2: Add new columns to donations ────────────────────
ALTER TABLE donations ADD COLUMN IF NOT EXISTS ngo_id UUID REFERENCES users(id);
ALTER TABLE donations ADD COLUMN IF NOT EXISTS assignment_time TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_location VARCHAR;

-- ── Step 3: Backfill pickup_location from pickup_address ────
UPDATE donations SET pickup_location = pickup_address WHERE pickup_location IS NULL AND pickup_address IS NOT NULL;

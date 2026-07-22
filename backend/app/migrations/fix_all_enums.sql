-- Complete database fix script for FoodBridge
-- This script fixes all enum and column issues

-- ============================================
-- PART 1: Fix users.ngo_id column
-- ============================================
DO $$
BEGIN
    -- Add ngo_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'ngo_id'
    ) THEN
        ALTER TABLE users ADD COLUMN ngo_id UUID REFERENCES users(id);
        RAISE NOTICE 'Added ngo_id column to users table';
    ELSE
        RAISE NOTICE 'ngo_id column already exists';
    END IF;
END $$;

-- ============================================
-- PART 2: Fix donationstatusenum values
-- ============================================
DO $$
DECLARE
    enum_oid OID;
BEGIN
    -- Get the enum OID
    SELECT oid INTO enum_oid FROM pg_type WHERE typname = 'donationstatusenum';
    
    IF enum_oid IS NOT NULL THEN
        -- Add lowercase 'assigned' if missing
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumtypid = enum_oid AND enumlabel = 'assigned'
        ) THEN
            ALTER TYPE donationstatusenum ADD VALUE 'assigned';
            RAISE NOTICE 'Added assigned to donationstatusenum';
        END IF;
        
        -- Add lowercase 'claimed' if missing
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumtypid = enum_oid AND enumlabel = 'claimed'
        ) THEN
            ALTER TYPE donationstatusenum ADD VALUE 'claimed';
            RAISE NOTICE 'Added claimed to donationstatusenum';
        END IF;
        
        -- Add lowercase 'in_progress' if missing
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumtypid = enum_oid AND enumlabel = 'in_progress'
        ) THEN
            ALTER TYPE donationstatusenum ADD VALUE 'in_progress';
            RAISE NOTICE 'Added in_progress to donationstatusenum';
        END IF;
        
        -- Add lowercase 'picked_up' if missing
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumtypid = enum_oid AND enumlabel = 'picked_up'
        ) THEN
            ALTER TYPE donationstatusenum ADD VALUE 'picked_up';
            RAISE NOTICE 'Added picked_up to donationstatusenum';
        END IF;
    ELSE
        RAISE NOTICE 'donationstatusenum type not found, may have been converted to VARCHAR';
    END IF;
END $$;

-- ============================================
-- PART 3: Fix freshnessstatusenum values
-- ============================================
DO $$
DECLARE
    enum_oid OID;
BEGIN
    -- Get the enum OID
    SELECT oid INTO enum_oid FROM pg_type WHERE typname = 'freshnessstatusenum';
    
    IF enum_oid IS NOT NULL THEN
        -- Add 'Unknown' if missing
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumtypid = enum_oid AND enumlabel = 'Unknown'
        ) THEN
            ALTER TYPE freshnessstatusenum ADD VALUE 'Unknown';
            RAISE NOTICE 'Added Unknown to freshnessstatusenum';
        END IF;
        
        -- Add 'Fresh' if missing
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumtypid = enum_oid AND enumlabel = 'Fresh'
        ) THEN
            ALTER TYPE freshnessstatusenum ADD VALUE 'Fresh';
            RAISE NOTICE 'Added Fresh to freshnessstatusenum';
        END IF;
        
        -- Add 'Risky' if missing
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumtypid = enum_oid AND enumlabel = 'Risky'
        ) THEN
            ALTER TYPE freshnessstatusenum ADD VALUE 'Risky';
            RAISE NOTICE 'Added Risky to freshnessstatusenum';
        END IF;
        
        -- Add 'Expired' if missing
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumtypid = enum_oid AND enumlabel = 'Expired'
        ) THEN
            ALTER TYPE freshnessstatusenum ADD VALUE 'Expired';
            RAISE NOTICE 'Added Expired to freshnessstatusenum';
        END IF;
    ELSE
        RAISE NOTICE 'freshnessstatusenum type not found, may have been converted to VARCHAR';
    END IF;
END $$;

-- ============================================
-- PART 4: Verify and report final state
-- ============================================
DO $$
BEGIN
    RAISE NOTICE '=== Final Enum State ===';
    
    -- Check donationstatusenum
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'donationstatusenum') THEN
        RAISE NOTICE 'donationstatusenum values: %', 
            (SELECT string_agg(enumlabel, ', ') FROM pg_enum WHERE enumtypid = 'donationstatusenum'::regtype);
    ELSE
        RAISE NOTICE 'donationstatusenum: converted to VARCHAR';
    END IF;
    
    -- Check freshnessstatusenum
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'freshnessstatusenum') THEN
        RAISE NOTICE 'freshnessstatusenum values: %', 
            (SELECT string_agg(enumlabel, ', ') FROM pg_enum WHERE enumtypid = 'freshnessstatusenum'::regtype);
    ELSE
        RAISE NOTICE 'freshnessstatusenum: converted to VARCHAR';
    END IF;
END $$;

-- ============================================
-- PART 5: Ensure all required columns exist
-- ============================================
DO $$
BEGIN
    -- Add missing columns to donations table
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS ngo_id UUID REFERENCES users(id);
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS volunteer_id UUID REFERENCES users(id);
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_status VARCHAR DEFAULT 'pending';
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_code VARCHAR;
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_verified BOOLEAN DEFAULT FALSE;
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_time TIMESTAMP;
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_time TIMESTAMP;
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS assignment_time TIMESTAMP;
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_location VARCHAR;
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS cancel_reason VARCHAR;
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS ai_confidence_score FLOAT;
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS image_timestamp TIMESTAMP;
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS image_hash VARCHAR(64);
    ALTER TABLE donations ADD COLUMN IF NOT EXISTS image_source VARCHAR(16);
    
    -- Add missing columns to users table
    ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'pending';
    ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lat FLOAT;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lng FLOAT;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS rating FLOAT DEFAULT 5.0;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS completed_deliveries INTEGER DEFAULT 0;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS volunteer_status VARCHAR DEFAULT 'pending';
    ALTER TABLE users ADD COLUMN IF NOT EXISTS availability VARCHAR DEFAULT 'available';
    
    RAISE NOTICE 'All columns verified/added successfully';
END $$;

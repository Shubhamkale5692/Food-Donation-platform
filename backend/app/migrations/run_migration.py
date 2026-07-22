#!/usr/bin/env python3
"""
Database migration script to fix all enum and column issues.
Run this script to apply all fixes to the database.
"""

import os
import sys

# Add the backend path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.infrastructure.database import engine, Base, get_db


def run_migration():
    """Run all database fixes."""

    migration_sql = """
-- ============================================
-- PART 1: Fix users.ngo_id column
-- ============================================
DO $$
BEGIN
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
-- PART 2: Add missing columns to users table
-- ============================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'pending';
ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lat FLOAT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lng FLOAT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS rating FLOAT DEFAULT 5.0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS completed_deliveries INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS volunteer_status VARCHAR DEFAULT 'pending';
ALTER TABLE users ADD COLUMN IF NOT EXISTS availability VARCHAR DEFAULT 'available';

-- ============================================
-- PART 3: Add missing columns to donations table
-- ============================================
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

-- ============================================
-- PART 4: Fix donationstatusenum values (lowercase)
-- ============================================
DO $$
DECLARE
    enum_oid OID;
BEGIN
    SELECT oid INTO enum_oid FROM pg_type WHERE typname = 'donationstatusenum';
    
    IF enum_oid IS NOT NULL THEN
        -- Add lowercase values
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = enum_oid AND enumlabel = 'assigned') THEN
            ALTER TYPE donationstatusenum ADD VALUE 'assigned';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = enum_oid AND enumlabel = 'claimed') THEN
            ALTER TYPE donationstatusenum ADD VALUE 'claimed';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = enum_oid AND enumlabel = 'in_progress') THEN
            ALTER TYPE donationstatusenum ADD VALUE 'in_progress';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = enum_oid AND enumlabel = 'picked_up') THEN
            ALTER TYPE donationstatusenum ADD VALUE 'picked_up';
        END IF;
    END IF;
END $$;

-- ============================================
-- PART 5: Fix freshnessstatusenum values
-- ============================================
DO $$
DECLARE
    enum_oid OID;
BEGIN
    SELECT oid INTO enum_oid FROM pg_type WHERE typname = 'freshnessstatusenum';
    
    IF enum_oid IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = enum_oid AND enumlabel = 'Unknown') THEN
            ALTER TYPE freshnessstatusenum ADD VALUE 'Unknown';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = enum_oid AND enumlabel = 'Fresh') THEN
            ALTER TYPE freshnessstatusenum ADD VALUE 'Fresh';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = enum_oid AND enumlabel = 'Risky') THEN
            ALTER TYPE freshnessstatusenum ADD VALUE 'Risky';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = enum_oid AND enumlabel = 'Expired') THEN
            ALTER TYPE freshnessstatusenum ADD VALUE 'Expired';
        END IF;
    END IF;
END $$;

-- ============================================
-- PART 6: Add message status columns (Phase 2)
-- ============================================
ALTER TABLE messages ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'sent';
ALTER TABLE messages ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS seen_at TIMESTAMP;
"""

    with engine.begin() as conn:
        print("Running database migrations...")
        conn.execute(text(migration_sql))
        print("Database migrations completed successfully!")

        # Verify fixes
        print("\n=== Verification ===")

        # Check users columns
        result = conn.execute(
            text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name IN ('ngo_id', 'status', 'availability', 'rating', 'completed_deliveries')
        """)
        )
        columns = [row[0] for row in result]
        print(f"Users columns present: {columns}")

        # Check donations columns
        result = conn.execute(
            text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'donations' AND column_name IN ('ngo_id', 'volunteer_id', 'delivery_status', 'otp_code', 'otp_verified')
        """)
        )
        columns = [row[0] for row in result]
        print(f"Donations columns present: {columns}")

        # Check enums
        result = conn.execute(
            text("""
            SELECT typname, string_agg(enumlabel, ', ') 
            FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE typname IN ('donationstatusenum', 'freshnessstatusenum')
            GROUP BY typname
        """)
        )
        for row in result:
            print(f"Enum {row[0]}: {row[1]}")

        # Check messages columns (Phase 2)
        result = conn.execute(
            text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'messages' AND column_name IN ('status', 'delivered_at', 'seen_at')
        """)
        )
        columns = [row[0] for row in result]
        print(f"Messages columns present: {columns}")


if __name__ == "__main__":
    print("Starting database migration...")
    print(f"Database URL: {engine.url}")
    try:
        run_migration()
        print("\nAll migrations completed!")
    except Exception as e:
        print(f"\nMigration error: {e}")
        print(
            "This might be expected if columns already exist or Docker is not running"
        )
        sys.exit(1)

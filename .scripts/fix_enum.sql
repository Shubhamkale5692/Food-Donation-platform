-- Fix donationstatusenum: add missing values that the Python model defines
-- This is safe to run multiple times due to the IF NOT EXISTS-style approach

DO $$
BEGIN
    -- Add 'assigned' if missing
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum WHERE enumlabel = 'assigned'
          AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'donationstatusenum')
    ) THEN
        ALTER TYPE donationstatusenum ADD VALUE 'assigned';
    END IF;

    -- Add 'claimed' if missing
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum WHERE enumlabel = 'claimed'
          AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'donationstatusenum')
    ) THEN
        ALTER TYPE donationstatusenum ADD VALUE 'claimed';
    END IF;

    -- Add 'in_progress' if missing
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum WHERE enumlabel = 'in_progress'
          AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'donationstatusenum')
    ) THEN
        ALTER TYPE donationstatusenum ADD VALUE 'in_progress';
    END IF;

    -- Add 'picked_up' if missing
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum WHERE enumlabel = 'picked_up'
          AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'donationstatusenum')
    ) THEN
        ALTER TYPE donationstatusenum ADD VALUE 'picked_up';
    END IF;
END
$$;

-- Verify result
SELECT enumlabel FROM pg_enum
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'donationstatusenum')
ORDER BY enumsortorder;

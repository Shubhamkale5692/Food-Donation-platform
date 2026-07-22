-- FoodBridge Database Migration
-- Run this script to add missing columns and enum values

-- Add missing columns to donations table
ALTER TABLE donations ADD COLUMN IF NOT EXISTS ngo_id UUID REFERENCES users(id);
ALTER TABLE donations ADD COLUMN IF NOT EXISTS volunteer_id UUID REFERENCES users(id);
ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_code VARCHAR(10);
ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_time TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_time TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS assignment_time TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_location VARCHAR(500);

-- Add index on status column for faster filtering
CREATE INDEX IF NOT EXISTS idx_donations_status ON donations(status);
CREATE INDEX IF NOT EXISTS idx_donations_ngo_id ON donations(ngo_id);
CREATE INDEX IF NOT EXISTS idx_donations_volunteer_id ON donations(volunteer_id);

-- Note: DonationStatusEnum values should be:
-- 'Pending', 'Accepted', 'Assigned', 'Claimed', 'Picked_Up', 'In-Transit', 'Completed', 'Cancelled'
-- If using PostgreSQL enum, run:
-- CREATE TYPE donation_status_enum AS ENUM ('Pending', 'Accepted', 'Assigned', 'Claimed', 'Picked_Up', 'In-Transit', 'Completed', 'Cancelled');
-- ALTER TABLE donations ALTER COLUMN status TYPE donation_status_enum USING status::donation_status_enum;

-- Verify the columns exist
SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'donations';

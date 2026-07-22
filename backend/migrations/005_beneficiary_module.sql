-- Migration 005: Beneficiary Module + Delivery Completion Workflow
-- NON-BREAKING: All fields are nullable, no existing data modified

-- ============================================================
-- 1. CREATE BENEFICIARIES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS beneficiaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) CHECK (type IN ('NGO', 'Shelter', 'Individual')) NOT NULL,
    address TEXT,
    latitude FLOAT,
    longitude FLOAT,
    contact_number VARCHAR(20),
    capacity INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create index for geospatial queries
CREATE INDEX IF NOT EXISTS idx_beneficiaries_location ON beneficiaries (latitude, longitude) WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_beneficiaries_type ON beneficiaries (type);
CREATE INDEX IF NOT EXISTS idx_beneficiaries_active ON beneficiaries (is_active) WHERE is_active = TRUE;

-- ============================================================
-- 2. EXTEND DONATIONS TABLE (Nullable Fields)
-- ============================================================
-- Add beneficiary_id FK (already has picked_up_at, delivered_at, received_at from lifecycle tracking)
ALTER TABLE donations ADD COLUMN IF NOT EXISTS beneficiary_id UUID REFERENCES beneficiaries(id);
ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_partner_id UUID REFERENCES users(id);
ALTER TABLE donations ADD COLUMN IF NOT EXISTS receiver_name VARCHAR(255);

-- Add indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_donations_beneficiary ON donations (beneficiary_id);
CREATE INDEX IF NOT EXISTS idx_donations_delivery_partner ON donations (delivery_partner_id);
CREATE INDEX IF NOT EXISTS idx_donations_receiver_name ON donations (receiver_name) WHERE receiver_name IS NOT NULL;

-- ============================================================
-- 3. ADD BENEFICIARY_TYPE TO EXISTING ENUM (if needed for reference)
-- Note: This is informational - the actual type is stored in beneficiaries table
-- ============================================================

-- ============================================================
-- 4. SEED SAMPLE BENEFICIARIES (Optional - for testing)
-- ============================================================
-- INSERT INTO beneficiaries (name, type, address, latitude, longitude, contact_number, capacity)
-- VALUES 
--     ('Hope Shelter', 'Shelter', '123 Shelter Road, Delhi', 28.6139, 77.2090, '+91-9876543210', 50),
--     ('Food for All NGO', 'NGO', '456 NGO Lane, Mumbai', 19.0760, 72.8777, '+91-9876543211', 100),
--     ('Anand Individual', 'Individual', '789 Home Street, Bangalore', 12.9716, 77.5946, '+91-9876543212', 10);

-- ============================================================
-- 5. NOTE: Existing columns already exist from lifecycle tracking
-- - picked_up_at (exists)
-- - delivered_at (exists)
-- - received_at (exists)
-- - otp_verified (exists)
-- ============================================================
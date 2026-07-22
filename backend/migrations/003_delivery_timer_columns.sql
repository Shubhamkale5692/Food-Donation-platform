-- ============================================================
-- FoodBridge – Delivery Timer Columns Migration
-- Adds columns for real-time delivery timer tracking.
--
-- Usage (Docker):
--   docker exec -i <postgres-container-name> psql -U postgres -d foodbridge < migrations/003_delivery_timer_columns.sql
--
-- Usage (local psql):
--   psql -U postgres -d foodbridge -f migrations/003_delivery_timer_columns.sql
-- ============================================================

-- ── donations table - delivery timer columns ───────────────────────────
ALTER TABLE donations ADD COLUMN IF NOT EXISTS start_time TIMESTAMP;
ALTER TABLE donations ADD COLUMN IF NOT EXISTS total_duration INTEGER;

-- ── indexes for timer queries ────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_donations_start_time ON donations(start_time);
CREATE INDEX IF NOT EXISTS idx_donations_total_duration ON donations(total_duration);

-- ── Verification ──────────────────────────────────────────────────────────────
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'donations' 
  AND column_name IN ('start_time', 'total_duration')
ORDER BY column_name;
"""
Patch for main.py to also add freshness_status and deliveries.status VARCHAR migrations.
"""

path = r"f:\Food Donation Platform\backend\app\main.py"
with open(path, "rb") as f:
    content = f.read().decode("utf-8")

OLD = "        # Fix donations.status column: ensure it is VARCHAR, not native ENUM"
NEW = """        # Fix enum columns: ensure they are VARCHAR, not native ENUM
        # This prevents SQLAlchemy from sending uppercase enum names to PostgreSQL
        for fix_sql in [
            \"\"\"DO $$ BEGIN
                IF (SELECT data_type FROM information_schema.columns
                    WHERE table_name='donations' AND column_name='status') != 'character varying' THEN
                    ALTER TABLE donations ALTER COLUMN status DROP DEFAULT;
                    ALTER TABLE donations ALTER COLUMN status TYPE VARCHAR(50) USING CAST(status AS VARCHAR(50));
                    ALTER TABLE donations ALTER COLUMN status SET DEFAULT 'pending';
                END IF;
            END $$;\"\"\",
            \"\"\"DO $$ BEGIN
                IF (SELECT data_type FROM information_schema.columns
                    WHERE table_name='donations' AND column_name='freshness_status') != 'character varying' THEN
                    ALTER TABLE donations ALTER COLUMN freshness_status DROP DEFAULT;
                    ALTER TABLE donations ALTER COLUMN freshness_status TYPE VARCHAR(50) USING CAST(freshness_status AS VARCHAR(50));
                    ALTER TABLE donations ALTER COLUMN freshness_status SET DEFAULT 'Unknown';
                END IF;
            END $$;\"\"\",
            \"\"\"DO $$ BEGIN
                IF (SELECT data_type FROM information_schema.columns
                    WHERE table_name='deliveries' AND column_name='status') != 'character varying' THEN
                    ALTER TABLE deliveries ALTER COLUMN status DROP DEFAULT;
                    ALTER TABLE deliveries ALTER COLUMN status TYPE VARCHAR(50) USING CAST(status AS VARCHAR(50));
                    ALTER TABLE deliveries ALTER COLUMN status SET DEFAULT 'Assigned';
                END IF;
            END $$;\"\"\",
        ]:
            conn.execute(text(fix_sql))
        # Old comment kept for reference"""

if OLD in content:
    content = content.replace(OLD, NEW)
    print("Patched main.py with all enum fixes")
else:
    # It may already have been partially patched, let's check if the old DO $$ block is there
    if "DO $$" in content and "donations.status" in content:
        print("main.py already has partial fix - keeping as is")
    else:
        print("WARNING: Could not find target pattern, skipping main.py patch")

with open(path, "wb") as f:
    f.write(content.encode("utf-8"))
print("Done!")

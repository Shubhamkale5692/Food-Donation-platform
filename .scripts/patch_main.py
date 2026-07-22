"""
Patch for main.py to add donations.status column VARCHAR migration on startup.
This ensures that when the container restarts, the status column is always VARCHAR.
"""
import re

path = r"f:\Food Donation Platform\backend\app\main.py"
with open(path, "rb") as f:
    content = f.read().decode("utf-8")

# Insert the donations.status VARCHAR migration after the existing migrations  
OLD = "        # Enums are handled by migrations_custom.py\r\n        logger.info(\"Auto-migrations successfully applied.\")"
NEW = """        # Fix donations.status column: ensure it is VARCHAR, not native ENUM
        # This prevents SQLAlchemy from sending uppercase enum names to PostgreSQL
        conn.execute(text(\"\"\"
            DO $$
            BEGIN
                IF (SELECT data_type FROM information_schema.columns 
                    WHERE table_name='donations' AND column_name='status') != 'character varying' THEN
                    ALTER TABLE donations ALTER COLUMN status DROP DEFAULT;
                    ALTER TABLE donations ALTER COLUMN status TYPE VARCHAR(50) USING CAST(status AS VARCHAR(50));
                    ALTER TABLE donations ALTER COLUMN status SET DEFAULT 'pending';
                END IF;
            END $$;
        \"\"\"))
        logger.info("Auto-migrations successfully applied.")"""

if OLD in content:
    content = content.replace(OLD, NEW)
    print("Patched main.py successfully")
else:
    print("Could not find target in main.py")

with open(path, "wb") as f:
    f.write(content.encode("utf-8"))
print("Done!")

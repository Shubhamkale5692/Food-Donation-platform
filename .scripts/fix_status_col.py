"""
Fix: Convert donations.status from native Postgres ENUM to VARCHAR(50)
so SQLAlchemy can store any string value without native enum constraints.
"""
import sys
sys.path.append(r"/app")
sys.stdout = open("/app/fix_status_col.txt", "w")
sys.stderr = sys.stdout

from app.infrastructure.database import engine
from sqlalchemy import text

print("=== Fixing donations.status column: ENUM -> VARCHAR ===")
try:
    with engine.begin() as conn:
        # Step 1: Drop the default constraint
        conn.execute(text("ALTER TABLE donations ALTER COLUMN status DROP DEFAULT;"))
        print("Dropped default constraint")
        
        # Step 2: Convert the column to VARCHAR (using CAST)
        conn.execute(text("ALTER TABLE donations ALTER COLUMN status TYPE VARCHAR(50) USING status::VARCHAR(50);"))
        print("Converted status column to VARCHAR(50)")
        
        # Step 3: Set a new default
        conn.execute(text("ALTER TABLE donations ALTER COLUMN status SET DEFAULT 'pending';"))
        print("Set new default 'pending'")
        
    print("Migration complete!")
    
    # Verify
    with engine.connect() as conn:
        result = conn.execute(text("SELECT CAST(status AS TEXT), COUNT(*) FROM donations GROUP BY status"))
        print(f"Current status counts: {dict(result.fetchall())}")
        
        result2 = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='donations' AND column_name='status'"))
        for row in result2:
            print(f"Column type: {row}")

except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    print(traceback.format_exc())

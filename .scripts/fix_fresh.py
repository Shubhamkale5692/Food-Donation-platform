"""
Fix: Convert donations.freshness_status from native Postgres ENUM to VARCHAR(50)
"""
import sys
sys.path.append(r"/app")
sys.stdout = open("/app/fix_fresh.txt", "w")
sys.stderr = sys.stdout

from app.infrastructure.database import engine
from sqlalchemy import text

print("=== Fixing donations.freshness_status column: ENUM -> VARCHAR ===")
try:
    with engine.begin() as conn:
        # Check current type
        r = conn.execute(text(
            "SELECT data_type FROM information_schema.columns WHERE table_name='donations' AND column_name='freshness_status'"
        ))
        row = r.fetchone()
        print(f"Current type: {row[0] if row else 'unknown'}")
        
        if row and row[0] != 'character varying':
            conn.execute(text("ALTER TABLE donations ALTER COLUMN freshness_status DROP DEFAULT;"))
            conn.execute(text("ALTER TABLE donations ALTER COLUMN freshness_status TYPE VARCHAR(50) USING CAST(freshness_status AS VARCHAR(50));"))
            conn.execute(text("ALTER TABLE donations ALTER COLUMN freshness_status SET DEFAULT 'Unknown';"))
            print("Converted freshness_status to VARCHAR(50)")
        else:
            print("freshness_status is already VARCHAR - skipping")
    
    # Also check and fix deliveries.status if it's a native enum
    with engine.begin() as conn:
        r = conn.execute(text(
            "SELECT data_type FROM information_schema.columns WHERE table_name='deliveries' AND column_name='status'"
        ))
        row = r.fetchone()
        print(f"\ndeliveries.status type: {row[0] if row else 'unknown'}")
        if row and row[0] != 'character varying':
            conn.execute(text("ALTER TABLE deliveries ALTER COLUMN status DROP DEFAULT;"))
            conn.execute(text("ALTER TABLE deliveries ALTER COLUMN status TYPE VARCHAR(50) USING CAST(status AS VARCHAR(50));"))
            conn.execute(text("ALTER TABLE deliveries ALTER COLUMN status SET DEFAULT 'Assigned';"))
            print("Converted deliveries.status to VARCHAR(50)")
        else:
            print("deliveries.status is already VARCHAR - skipping")
            
    print("\nDONE")
    
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    print(traceback.format_exc())

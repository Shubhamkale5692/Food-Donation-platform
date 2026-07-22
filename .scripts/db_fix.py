import sys
sys.path.append(r"/app")
sys.stdout = open("/app/db_fix.txt", "w")
sys.stderr = sys.stdout

from app.infrastructure.database import engine
from sqlalchemy import text

print("=== Full DB Enum & Data Fix ===")

with engine.connect() as conn:
    # Step 1: Show current enum labels
    r = conn.execute(text("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'donationstatusenum') ORDER BY enumsortorder"))
    print(f"Current enums: {[row[0] for row in r]}")

    # Step 2: Add lowercase 'pending', 'accepted', 'cancelled', 'completed' if missing
    lowercases = ['pending', 'accepted', 'assigned', 'claimed', 'in_progress', 'picked_up', 'completed', 'cancelled']
    for val in lowercases:
        r2 = conn.execute(text(f"SELECT 1 FROM pg_enum WHERE enumlabel = '{val}' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'donationstatusenum')"))
        if r2.fetchone() is None:
            try:
                conn.execute(text(f"ALTER TYPE donationstatusenum ADD VALUE '{val}'"))
                print(f"Added enum value: '{val}'")
            except Exception as e:
                print(f"Error adding '{val}': {e}")
        else:
            print(f"Enum value '{val}' already exists")

    conn.commit()

print("\n=== Updating existing donation records - uppercase to lowercase ===")
with engine.begin() as conn:
    # Convert old uppercase enum values to lowercase
    updates = [
        ("UPDATE donations SET status = 'pending' WHERE CAST(status AS TEXT) = 'PENDING'", ),
        ("UPDATE donations SET status = 'accepted' WHERE CAST(status AS TEXT) = 'ACCEPTED'", ),
        ("UPDATE donations SET status = 'assigned' WHERE CAST(status AS TEXT) = 'ASSIGNED'", ),
        ("UPDATE donations SET status = 'completed' WHERE CAST(status AS TEXT) = 'COMPLETED'", ),
        ("UPDATE donations SET status = 'cancelled' WHERE CAST(status AS TEXT) = 'CANCELLED'", ),
        ("UPDATE donations SET status = 'in_progress' WHERE CAST(status AS TEXT) = 'IN_TRANSIT'", ),
    ]
    for (sql,) in updates:
        try:
            result = conn.execute(text(sql))
            print(f"Updated {result.rowcount} rows: {sql[:50]}")
        except Exception as e:
            print(f"Error: {e} for SQL: {sql[:50]}")

print("\n=== Final State ===")
with engine.connect() as conn:
    r = conn.execute(text("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'donationstatusenum') ORDER BY enumsortorder"))
    print(f"Final enum labels: {[row[0] for row in r]}")

    r2 = conn.execute(text("SELECT CAST(status AS TEXT), COUNT(*) FROM donations GROUP BY status"))
    print(f"Donation status counts: {dict(r2.fetchall())}")

print("DONE")

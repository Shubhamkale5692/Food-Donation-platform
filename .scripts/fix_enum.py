import sys
sys.path.append(r"/app")
sys.stdout = open("/app/enum_check.txt", "w")
sys.stderr = sys.stdout

from app.infrastructure.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'donationstatusenum') ORDER BY enumsortorder"
    ))
    rows = list(result)
    print(f"Current donationstatusenum values: {rows}")

    # Add missing values
    missing = ['assigned', 'claimed', 'in_progress', 'picked_up']
    existing = [r[0] for r in rows]
    for val in missing:
        if val not in existing:
            try:
                conn.execute(text(f"ALTER TYPE donationstatusenum ADD VALUE '{val}'"))
                print(f"Added '{val}' to donationstatusenum")
            except Exception as e:
                print(f"ERROR adding '{val}': {e}")
        else:
            print(f"'{val}' already exists")
    conn.commit()

# Check final state
with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'donationstatusenum') ORDER BY enumsortorder"
    ))
    print(f"Final enum values: {[r[0] for r in result]}")

print("DONE")

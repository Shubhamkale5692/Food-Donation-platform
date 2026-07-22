from sqlalchemy import text
from app.infrastructure.database import SessionLocal

db = SessionLocal()
try:
    # Check for inconsistent data: decision set but food_quality NULL
    result = db.execute(
        text(
            "SELECT id, decision, food_quality FROM donations WHERE decision IS NOT NULL AND food_quality IS NULL"
        )
    )
    rows = result.fetchall()
    print("=== INCONSISTENT DATA (decision set, food_quality NULL) ===")
    print(f"Count: {len(rows)}")
    print("-" * 60)
    for row in rows:
        print(f"{row[0]} | {row[1]} | {row[2]}")

    # Also check total counts
    result2 = db.execute(
        text("SELECT COUNT(*) FROM donations WHERE decision IS NOT NULL")
    )
    tested_count = result2.scalar()
    print(f"\nTotal tested donations: {tested_count}")

    result3 = db.execute(text("SELECT COUNT(*) FROM donations WHERE decision IS NULL"))
    untested_count = result3.scalar()
    print(f"Total untested donations: {untested_count}")

except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()

import sys
import traceback

sys.path.append(r"F:\Food Donation Platform\backend")

try:
    from app.infrastructure.database import SessionLocal
    from app.domain import models
    import uuid

    db = SessionLocal()
    try:
        donation_id = uuid.UUID("55f0bf96-85a6-4f05-933b-9f9912bba779")
        donation = (
            db.query(models.Donation).filter(models.Donation.id == donation_id).first()
        )
        if donation:
            print(f"FOUND: {donation.food_type}, status={donation.status}")
        else:
            print("Donation NOT FOUND")

        print("\n--- Sample donations ---")
        for d in db.query(models.Donation).limit(5).all():
            print(f"{d.id} - {d.food_type} - {d.status}")
    finally:
        db.close()
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()

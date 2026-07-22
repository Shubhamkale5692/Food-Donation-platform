import sys

sys.path.append(r"/app")

import uuid
import sys

sys.stdout = open("/app/output.txt", "w")
sys.stderr = sys.stdout

import logging

root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
root.addHandler(handler)
from app.infrastructure.database import SessionLocal, engine
from app.domain import models
from app.services import donation_service

models.Base.metadata.create_all(bind=engine)


def run_tests():
    db = SessionLocal()
    try:
        # Cleanup
        db.query(models.Delivery).filter(
            models.Delivery.donation.has(food_type="test-food-12345")
        ).delete()
        db.query(models.Donation).filter(
            models.Donation.food_type == "test-food-12345"
        ).delete()
        db.query(models.User).filter(
            models.User.email.like("test%@example.com")
        ).delete()
        db.commit()

        # 1. Create Donor, NGO, Volunteer
        donor = models.User(
            id=uuid.uuid4(),
            email=f"testdonor_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="pw",
            role=models.RoleEnum.DONOR,
            is_active=True,
            trust_score=100,
        )
        ngo = models.User(
            id=uuid.uuid4(),
            email=f"testngo_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="pw",
            role=models.RoleEnum.NGO,
            is_active=True,
            is_verified=True,
        )
        vol = models.User(
            id=uuid.uuid4(),
            email=f"testvol_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="pw",
            role=models.RoleEnum.VOLUNTEER,
            is_active=True,
            volunteer_status="approved",
            status="approved",
            availability="available",
            ngo_id=ngo.id,
        )

        db.add_all([donor, ngo, vol])
        db.commit()

        # 2. Donor Creates Donation
        from app.domain.schemas import DonationCreate
        from datetime import datetime

        donation_in = DonationCreate(
            food_type="test-food-12345",
            quantity="10",
            expiry_time=datetime.utcnow(),
            pickup_address="Test Ave",
        )
        donation = donation_service.create_donation(db, donation_in, donor.id)
        print("Created donation:", donation.id, donation.status)

        # 3. NGO Accepts Donation
        donation = donation_service.claim_donation(db, donation.id, ngo.id)
        print(f"Claimed donation result: {donation}")
        print(f"Donation status is: {donation.status} (type: {type(donation.status)})")
        print(
            f"Expected ACCEPTED is: {models.DonationStatusEnum.ACCEPTED} (type: {type(models.DonationStatusEnum.ACCEPTED)})"
        )
        print(
            f"Are they equal? {donation.status == models.DonationStatusEnum.ACCEPTED}"
        )

        # Manually check conditions before assignment
        db_donation = db.get(models.Donation, donation.id)
        print(f"From DB again: {db_donation.status}")

        # 4. NGO Assigns Volunteer
        delivery = donation_service.assign_volunteer(db, donation.id, ngo.id, vol.id)
        print("Assignment result:", delivery)
        assert delivery is not None, "assign_volunteer returned None!"
        assert delivery.status == models.DeliveryStatusEnum.ASSIGNED, (
            "Delivery should be ASSIGNED"
        )

        db.refresh(donation)
        assert donation.status == models.DonationStatusEnum.ASSIGNED, (
            "Donation should be ASSIGNED"
        )
        assert donation.delivery_status == "assigned", (
            "delivery_status should be 'assigned'"
        )

        db.refresh(vol)
        assert vol.availability == "busy", "Volunteer should be busy"

        # 5. Vol Generates OTP
        donation.otp_code = "123456"
        delivery.otp = "123456"
        db.commit()

        # 6. Vol Verifies OTP
        delivery = donation_service.verify_delivery_otp(
            db, donation.id, "123456", vol.id
        )
        assert delivery.status == models.DeliveryStatusEnum.PICKED_UP, (
            "Delivery should be PICKED_UP"
        )

        db.refresh(donation)
        assert donation.status == models.DonationStatusEnum.IN_PROGRESS, (
            "Donation should be IN_PROGRESS"
        )

        # 7. Vol completes Delivery
        donation = donation_service.update_donation_status(
            db, donation.id, models.DonationStatusEnum.COMPLETED
        )
        assert donation.status == models.DonationStatusEnum.COMPLETED, (
            "Donation should be COMPLETED"
        )
        assert donation.delivery_status == "delivered", (
            "Delivery status string should be delivered"
        )

        db.refresh(delivery)
        assert delivery.status == models.DeliveryStatusEnum.DELIVERED, (
            "Delivery should be DELIVERED"
        )

        db.refresh(vol)
        assert vol.availability == "available", "Volunteer should be available again"

        print("ALL TESTS PASSED: ASSIGNMENT END-TO-END WORKED FLAWLESSLY")

    except Exception as e:
        import traceback

        with open("/app/test_out.txt", "w") as f:
            f.write("TEST FAILED: " + str(e) + "\n")
            f.write(traceback.format_exc())
        print(f"TEST FAILED. See /app/test_out.txt")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run_tests()

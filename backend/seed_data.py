import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.infrastructure.database import SessionLocal, engine, Base
from app.domain import models
from app.core.security import get_password_hash
from datetime import datetime, timezone, timedelta
import uuid


def seed_data():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # Check if data already exists
        existing_users = db.query(models.User).count()
        if existing_users > 0:
            print(f"Database already has {existing_users} users. Skipping seed.")
            print("If you want to re-seed, clear the database first.")
            return

        print("Seeding data...")

        # 1. Create Admin User
        admin = models.User(
            id=uuid.uuid4(),
            email="admin@foodbridge.org",
            password_hash=get_password_hash("admin123"),
            role=models.RoleEnum.ADMIN,
            name="System Admin",
            is_active=True,
            is_verified=True,
        )
        db.add(admin)

        # 2. Create NGOs
        ngo1 = models.User(
            id=uuid.uuid4(),
            email="ngo1@foodbridge.org",
            password_hash=get_password_hash("ngo123"),
            role=models.RoleEnum.NGO,
            name="Food For All Foundation",
            is_active=True,
            is_verified=True,
        )
        db.add(ngo1)

        ngo2 = models.User(
            id=uuid.uuid4(),
            email="ngo2@foodbridge.org",
            password_hash=get_password_hash("ngo123"),
            role=models.RoleEnum.NGO,
            name=" hunger Relief Organization",
            is_active=True,
            is_verified=True,
        )
        db.add(ngo2)

        db.flush()

        # Create NGO Profiles
        ngo_profile1 = models.Profile(
            user_id=ngo1.id,
            name="Food For All Foundation",
            phone="+1-555-0101",
            address="123 Charity Lane, New York, NY 10001",
            latitude=40.7128,
            longitude=-74.0060,
        )
        db.add(ngo_profile1)

        ngo_profile2 = models.Profile(
            user_id=ngo2.id,
            name="Hunger Relief Organization",
            phone="+1-555-0102",
            address="456 Hope Street, Los Angeles, CA 90001",
            latitude=34.0522,
            longitude=-118.2437,
        )
        db.add(ngo_profile2)

        # 3. Create Donors
        donors = []
        donor_data = [
            ("donor1@foodbridge.org", "John Smith"),
            ("donor2@foodbridge.org", "Sarah Johnson"),
            ("donor3@foodbridge.org", "Mike Brown"),
            ("donor4@foodbridge.org", "Emily Davis"),
            ("donor5@foodbridge.org", "Robert Wilson"),
        ]

        for email, name in donor_data:
            donor = models.User(
                id=uuid.uuid4(),
                email=email,
                password_hash=get_password_hash("donor123"),
                role=models.RoleEnum.DONOR,
                name=name,
                is_active=True,
                is_verified=True,
            )
            db.add(donor)
            donors.append(donor)

        db.flush()

        # Create Donor Profiles
        donor_profiles = [
            (donors[0], "555-0101", "100 Main St, New York, NY", 40.7580, -73.9855),
            (donors[1], "555-0102", "200 Oak Ave, Brooklyn, NY", 40.6892, -73.9442),
            (donors[2], "555-0103", "300 Pine Rd, Queens, NY", 40.7282, -73.7949),
            (donors[3], "555-0104", "400 Elm Blvd, Bronx, NY", 40.8448, -73.8648),
            (
                donors[4],
                "555-0105",
                "500 Maple Dr, Staten Island, NY",
                40.5795,
                -74.1502,
            ),
        ]

        for donor, phone, address, lat, lng in donor_profiles:
            profile = models.Profile(
                user_id=donor.id,
                name=donor.name,
                phone=phone,
                address=address,
                latitude=lat,
                longitude=lng,
            )
            db.add(profile)

        db.flush()

        # 4. Create Volunteers
        volunteers = []
        volunteer_data = [
            ("vol1@foodbridge.org", "Alex Volunteer", ngo1.id),
            ("vol2@foodbridge.org", "Betty Helper", ngo1.id),
            ("vol3@foodbridge.org", "Charlie Runner", ngo2.id),
            ("vol4@foodbridge.org", "Diana Courier", ngo2.id),
            ("vol5@foodbridge.org", "Edward Driver", ngo1.id),
        ]

        for email, name, assigned_ngo in volunteer_data:
            vol = models.User(
                id=uuid.uuid4(),
                email=email,
                password_hash=get_password_hash("vol123"),
                role=models.RoleEnum.VOLUNTEER,
                name=name,
                ngo_id=assigned_ngo,
                volunteer_status="approved",
                status="approved",
                availability="available",
                is_active=True,
                completed_deliveries=0,
                rating=5.0,
            )
            db.add(vol)
            volunteers.append(vol)

        db.flush()

        # Create Volunteer Profiles
        vol_profiles = [
            (volunteers[0], "111-0101", "101 Volunteer St", 40.7200, -73.9800),
            (volunteers[1], "111-0102", "102 Helper Ave", 40.7300, -73.9900),
            (volunteers[2], "111-0103", "103 Runner Blvd", 34.0600, -118.2500),
            (volunteers[3], "111-0104", "104 Courier Way", 34.0700, -118.2600),
            (volunteers[4], "111-0105", "105 Driver Lane", 40.7400, -73.9700),
        ]

        for vol, phone, address, lat, lng in vol_profiles:
            profile = models.Profile(
                user_id=vol.id,
                name=vol.name,
                phone=phone,
                address=address,
                latitude=lat,
                longitude=lng,
            )
            db.add(profile)

        db.flush()

        print(f"Created {len(donors)} donors, {len(volunteers)} volunteers, 2 NGOs")

        # 5. Create Donations with different statuses
        now = datetime.now(timezone.utc)

        # Pending donations (should show in NGO pending list)
        pending_foods = [
            ("Rice", 50, now + timedelta(hours=6)),
            ("Bread", 30, now + timedelta(hours=4)),
            ("Vegetables", 40, now + timedelta(hours=3)),
            ("Fruits", 25, now + timedelta(hours=5)),
            ("Canned Goods", 60, now + timedelta(hours=24)),
        ]

        for i, (food, qty, expiry) in enumerate(pending_foods):
            donation = models.Donation(
                donor_id=donors[i % len(donors)].id,
                food_type=food,
                quantity=qty,
                expiry_time=expiry,
                status=models.DonationStatusEnum.PENDING,
                freshness_status=models.FreshnessStatusEnum.FRESH,
                latitude=donor_profiles[i % len(donor_profiles)][3],
                longitude=donor_profiles[i % len(donor_profiles)][4],
                created_at=now - timedelta(hours=i),
            )
            db.add(donation)

        db.flush()

        # Accepted donations (claimed by NGOs)
        accepted_foods = [
            ("Cooked Pasta", 20, now + timedelta(hours=2)),
            ("Sandwiches", 15, now + timedelta(hours=3)),
            ("Milk", 10, now + timedelta(hours=1)),
        ]

        for i, (food, qty, expiry) in enumerate(accepted_foods):
            donation = models.Donation(
                donor_id=donors[i].id,
                food_type=food,
                quantity=qty,
                expiry_time=expiry,
                status=models.DonationStatusEnum.ACCEPTED,
                freshness_status=models.FreshnessStatusEnum.FRESH,
                latitude=donor_profiles[i][3],
                longitude=donor_profiles[i][4],
                ngo_id=ngo1.id,
                created_at=now - timedelta(hours=i + 5),
            )
            db.add(donation)

        db.flush()

        # Assigned donations (with volunteers assigned)
        assigned_foods = [
            ("Pizza Slices", 40, now + timedelta(hours=1)),
            ("Salad", 25, now + timedelta(hours=2)),
        ]

        for i, (food, qty, expiry) in enumerate(assigned_foods):
            donation = models.Donation(
                donor_id=donors[i + 3].id,
                food_type=food,
                quantity=qty,
                expiry_time=expiry,
                status=models.DonationStatusEnum.ASSIGNED,
                freshness_status=models.FreshnessStatusEnum.FRESH,
                latitude=donor_profiles[i + 3][3],
                longitude=donor_profiles[i + 3][4],
                ngo_id=ngo1.id,
                volunteer_id=volunteers[i].id,
                created_at=now - timedelta(hours=i + 10),
            )
            db.add(donation)

        db.flush()

        # In Progress donations
        in_progress_foods = [
            ("Soup", 30, now + timedelta(hours=1)),
        ]

        for i, (food, qty, expiry) in enumerate(in_progress_foods):
            donation = models.Donation(
                donor_id=donors[4].id,
                food_type=food,
                quantity=qty,
                expiry_time=expiry,
                status=models.DonationStatusEnum.IN_PROGRESS,
                freshness_status=models.FreshnessStatusEnum.FRESH,
                latitude=donor_profiles[4][3],
                longitude=donor_profiles[4][4],
                ngo_id=ngo1.id,
                volunteer_id=volunteers[4].id,
                donation_received=True,
                delivery_status="in_transit",
                created_at=now - timedelta(hours=15),
            )
            db.add(donation)

        db.flush()

        # Completed donations (history)
        completed_foods = [
            ("Rice Bags", 100, now - timedelta(days=1)),
            ("Bread Loaves", 50, now - timedelta(days=2)),
            ("Veggie Boxes", 75, now - timedelta(days=3)),
            ("Fruit Baskets", 60, now - timedelta(days=4)),
            ("Canned Food", 80, now - timedelta(days=5)),
            ("Pasta Packs", 45, now - timedelta(days=6)),
            ("Cereal Boxes", 35, now - timedelta(days=7)),
            ("Milk Cartons", 40, now - timedelta(days=8)),
        ]

        for i, (food, qty, created) in enumerate(completed_foods):
            donation = models.Donation(
                donor_id=donors[i % len(donors)].id,
                food_type=food,
                quantity=qty,
                expiry_time=created + timedelta(hours=5),
                status=models.DonationStatusEnum.COMPLETED,
                freshness_status=models.FreshnessStatusEnum.FRESH,
                latitude=donor_profiles[i % len(donor_profiles)][3],
                longitude=donor_profiles[i % len(donor_profiles)][4],
                ngo_id=ngo1.id if i % 2 == 0 else ngo2.id,
                volunteer_id=volunteers[i % len(volunteers)].id,
                created_at=created,
                delivery_time=created + timedelta(hours=2),
                delivery_status="delivered",
            )
            db.add(donation)

        db.flush()

        # Create Delivery records for assigned/in-progress/completed donations
        all_donations = db.query(models.Donation).all()
        for donation in all_donations:
            if donation.ngo_id and donation.volunteer_id:
                # Check if delivery already exists
                existing_delivery = (
                    db.query(models.Delivery)
                    .filter(models.Delivery.donation_id == donation.id)
                    .first()
                )

                if not existing_delivery:
                    delivery_status_map = {
                        models.DonationStatusEnum.ASSIGNED: models.DeliveryStatusEnum.ASSIGNED,
                        models.DonationStatusEnum.IN_PROGRESS: models.DeliveryStatusEnum.IN_PROGRESS,
                        models.DonationStatusEnum.COMPLETED: models.DeliveryStatusEnum.DELIVERED,
                    }

                    delivery = models.Delivery(
                        donation_id=donation.id,
                        ngo_id=donation.ngo_id,
                        volunteer_id=donation.volunteer_id,
                        status=delivery_status_map.get(
                            donation.status, models.DeliveryStatusEnum.PENDING
                        ),
                        assigned_at=donation.created_at,
                        completed_at=donation.delivery_time,
                    )
                    db.add(delivery)

        db.flush()

        # Update volunteer completed deliveries count
        completed_count_by_vol = {}
        for donation in (
            db.query(models.Donation)
            .filter(models.Donation.status == models.DonationStatusEnum.COMPLETED)
            .all()
        ):
            if donation.volunteer_id:
                completed_count_by_vol[donation.volunteer_id] = (
                    completed_count_by_vol.get(donation.volunteer_id, 0) + 1
                )

        for vol in volunteers:
            if vol.id in completed_count_by_vol:
                vol.completed_deliveries = completed_count_by_vol[vol.id]

        db.commit()

        print("Seed data created successfully!")
        print("\n=== Test Accounts ===")
        print("Admin: admin@foodbridge.org / admin123")
        print("NGO 1: ngo1@foodbridge.org / ngo123")
        print("NGO 2: ngo2@foodbridge.org / ngo123")
        print("Donor: donor1@foodbridge.org / donor123")
        print("Volunteer: vol1@foodbridge.org / vol123")

    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()

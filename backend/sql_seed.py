import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import uuid

# Direct database connection (no ORM needed)
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "postgres",
    "dbname": "foodbridge",
}


def seed_extra_data():
    print("Connecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Check existing data
        cursor.execute("SELECT COUNT(*) as cnt FROM donations")
        before_count = cursor.fetchone()["cnt"]
        print(f"Before: {before_count} donations")

        # Get donor IDs
        cursor.execute("SELECT id FROM users WHERE role = 'DONOR'")
        donors = [row["id"] for row in cursor.fetchall()]

        if not donors:
            print("No donors found! Cannot seed donations.")
            return

        # Get NGO and volunteer IDs
        cursor.execute("SELECT id FROM users WHERE role = 'NGO' LIMIT 1")
        ngo_id = cursor.fetchone()["id"] if cursor.rowcount > 0 else None

        cursor.execute("SELECT id FROM users WHERE role = 'VOLUNTEER' LIMIT 1")
        vol_id = cursor.fetchone()["id"] if cursor.rowcount > 0 else None

        print(f"Using NGO: {ngo_id}, Volunteer: {vol_id}")

        # Add pending donations for different donors
        food_types = [
            "Fresh Bread",
            "Cooked Rice",
            "Vegetables",
            "Fruits",
            "Milk",
            "Yogurt",
            "Canned Soup",
        ]
        addresses = [
            "100 Main St",
            "200 Oak Ave",
            "300 Pine Rd",
            "400 Elm Blvd",
            "500 Maple Dr",
        ]

        for i, donor_id in enumerate(donors[:5]):
            food = food_types[i % len(food_types)]
            qty = 5 + (i * 5)  # 5, 10, 15, 20, 25
            lat = 40.7128 + (i * 0.01)
            lng = -74.0060 + (i * 0.01)

            cursor.execute(
                """
                INSERT INTO donations (id, donor_id, food_type, quantity, expiry_time, 
                    status, freshness_status, latitude, longitude, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    str(uuid.uuid4()),
                    donor_id,
                    food,
                    qty,
                    datetime.now() + timedelta(hours=6 + i * 2),
                    "pending",
                    "Fresh",
                    lat,
                    lng,
                    datetime.now() - timedelta(hours=i),
                ),
            )
            print(f"Added pending donation: {food} x{qty}")

        # Add completed donations for history tab
        for i, donor_id in enumerate(donors[:5]):
            food = food_types[(i + 3) % len(food_types)]
            qty = 10 + (i * 10)  # 10, 20, 30, 40, 50

            cursor.execute(
                """
                INSERT INTO donations (id, donor_id, food_type, quantity, expiry_time, 
                    status, freshness_status, latitude, longitude, ngo_id, volunteer_id, 
                    created_at, delivery_time, delivery_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    str(uuid.uuid4()),
                    donor_id,
                    food,
                    qty,
                    datetime.now() - timedelta(days=1),
                    "completed",
                    "Fresh",
                    40.75 + i * 0.01,
                    -73.99 + i * 0.01,
                    ngo_id,
                    vol_id,
                    datetime.now() - timedelta(days=i + 1),
                    datetime.now() - timedelta(days=i),
                    "delivered",
                ),
            )
            print(f"Added completed donation: {food} x{qty}")

        # Add accepted/assigned donations for active tabs
        if ngo_id and vol_id:
            for i, donor_id in enumerate(donors[:3]):
                food = food_types[i]
                qty = 15 + (i * 5)
                status = "accepted" if i < 2 else "assigned"

                cursor.execute(
                    """
                    INSERT INTO donations (id, donor_id, food_type, quantity, expiry_time, 
                        status, freshness_status, latitude, longitude, ngo_id, volunteer_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        str(uuid.uuid4()),
                        donor_id,
                        food,
                        qty,
                        datetime.now() + timedelta(hours=4 + i * 2),
                        status,
                        "Fresh",
                        40.72 + i * 0.01,
                        -73.98 + i * 0.01,
                        ngo_id,
                        vol_id if status == "assigned" else None,
                        datetime.now() - timedelta(hours=i + 2),
                    ),
                )
                print(f"Added {status} donation: {food} x{qty}")

        # Ensure profiles exist for all users
        cursor.execute("""
            INSERT INTO profiles (user_id, name, phone, address, latitude, longitude)
            SELECT id, COALESCE(name, split_part(email, '@', 1)), 
                '+1-555-' || floor(random()*9000+1000)::text,
                '123 Main St',
                40.7128 + random()*0.1,
                -74.0060 + random()*0.1
            FROM users 
            WHERE id NOT IN (SELECT user_id FROM profiles WHERE user_id IS NOT NULL)
        """)
        print("Ensured all users have profiles")

        # Verify final count
        cursor.execute("SELECT COUNT(*) as cnt FROM donations")
        after_count = cursor.fetchone()["cnt"]
        print(f"After: {after_count} donations")
        print(f"Added {after_count - before_count} new donations")

        # Show status breakdown
        cursor.execute(
            "SELECT status, COUNT(*) as cnt FROM donations GROUP BY status ORDER BY status"
        )
        print("\nDonation status breakdown:")
        for row in cursor.fetchall():
            print(f"  {row['status']}: {row['cnt']}")

    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    seed_extra_data()

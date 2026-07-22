import os
import sys
from sqlalchemy import create_engine, text

# Add the backend to the path
sys.path.append('f:/Food Donation Platform/backend')

from app.db.session import SQLALCHEMY_DATABASE_URL

def check_db():
    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        with engine.connect() as conn:
            # Check users
            user_count = conn.execute(text("SELECT count(*) FROM users")).scalar()
            roles = conn.execute(text("SELECT role, count(*) FROM users GROUP BY role")).fetchall()
            
            # Check donations
            donation_count = conn.execute(text("SELECT count(*) FROM donations")).scalar()
            donation_statuses = conn.execute(text("SELECT status, count(*) FROM donations GROUP BY status")).fetchall()
            
            # Check deliveries
            delivery_count = conn.execute(text("SELECT count(*) FROM deliveries")).scalar()
            
            print(f"Total Users: {user_count}")
            for r in roles:
                print(f"  Role {r[0]}: {r[1]}")
            
            print(f"Total Donations: {donation_count}")
            for s in donation_statuses:
                print(f"  Status {s[0]}: {s[1]}")
                
            print(f"Total Deliveries: {delivery_count}")
            
    except Exception as e:
        print(f"Error connecting to DB: {e}")

if __name__ == "__main__":
    check_db()

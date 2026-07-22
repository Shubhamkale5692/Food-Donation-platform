
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.domain.models import Beneficiary, User, Profile

# Database connection
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/foodbridge"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def fix_coordinates():
    db = SessionLocal()
    try:
        # Fix Beneficiaries without coordinates
        beneficiaries = db.query(Beneficiary).filter(
            (Beneficiary.latitude == None) | (Beneficiary.longitude == None)
        ).all()
        
        print(f"Found {len(beneficiaries)} beneficiaries missing coordinates.")
        for b in beneficiaries:
            # Set to some default coordinates (e.g., Pune, India)
            b.latitude = 18.5204 + (uuid.uuid4().int % 1000) / 100000.0
            b.longitude = 73.8567 + (uuid.uuid4().int % 1000) / 100000.0
            print(f"Updated Beneficiary {b.name} ({b.id}) with coords: {b.latitude}, {b.longitude}")

        # Fix NGO Profiles without coordinates
        profiles = db.query(Profile).filter(
            (Profile.latitude == None) | (Profile.longitude == None)
        ).all()
        
        print(f"Found {len(profiles)} profiles missing coordinates.")
        for p in profiles:
            p.latitude = 18.5204 + (uuid.uuid4().int % 1000) / 100000.0
            p.longitude = 73.8567 + (uuid.uuid4().int % 1000) / 100000.0
            print(f"Updated Profile for User ID {p.user_id} with coords: {p.latitude}, {p.longitude}")

        db.commit()
        print("Successfully updated all missing coordinates.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_coordinates()

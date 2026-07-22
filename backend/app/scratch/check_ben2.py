import sys
import os

sys.path.append(os.path.abspath('f:/Food Donation Platform/backend'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.infrastructure.database import SQLALCHEMY_DATABASE_URL
from app.domain import models

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

print("Checking Beneficiaries:")
bens = db.query(models.Beneficiary).all()
for b in bens:
    print(f"ID: {b.id}, Name: {b.name}, Lat: {b.latitude}, Lng: {b.longitude}")

print("\nChecking Donations with Beneficiaries:")
dons = db.query(models.Donation).filter(models.Donation.beneficiary_id != None).all()
for d in dons:
    print(f"Donation ID: {d.id}, Beneficiary ID: {d.beneficiary_id}, task_type: {d.task_type}, dist_status: {d.distribution_status}")

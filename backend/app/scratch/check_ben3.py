import sys
import os

sys.path.append(os.path.abspath('f:/Food Donation Platform/backend'))

from app.infrastructure.database import SessionLocal
from app.domain import models

db = SessionLocal()

print("Checking Beneficiaries:")
bens = db.query(models.Beneficiary).all()
for b in bens:
    print(f"ID: {b.id}, Name: {b.name}, Lat: {b.latitude}, Lng: {b.longitude}")

print("\nChecking Donations with Beneficiaries:")
dons = db.query(models.Donation).filter(models.Donation.beneficiary_id != None).all()
for d in dons:
    print(f"Donation ID: {d.id}, Beneficiary ID: {d.beneficiary_id}, task_type: {d.task_type}, dist_status: {d.distribution_status}")

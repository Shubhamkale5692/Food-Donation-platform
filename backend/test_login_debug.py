"""
Quick test script to debug login issues.
Run: python test_login_debug.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.infrastructure.database import SessionLocal
from app.services import auth_service
from app.core import security
from app.domain import models


def test_login(email, password):
    db = SessionLocal()
    try:
        print(f"\n=== Testing login for: {email} ===")

        # Find user
        user = auth_service.get_user_by_email(db, email)
        if not user:
            print("❌ User NOT FOUND in database")
            return

        print(f"✓ User found: ID={user.id}, Role={user.role}")
        print(f"  is_active={user.is_active}, is_verified={user.is_verified}")
        print(f"  volunteer_status={user.volunteer_status}")

        # Check password hash format
        print(f"\n  Password hash (first 60 chars): {user.password_hash[:60]}...")

        # Verify password
        result = security.verify_password(password, user.password_hash)
        print(f"  Password verification: {result}")

        if not result:
            print("\n❌ Password MISMATCH!")
            print("\nTrying to understand why...")

            # Try with a simple test
            test_hash = security.get_password_hash("test123")
            print(f"  New hash format: {test_hash[:60]}...")

            # Compare formats
            old_prefix = user.password_hash[:4]
            new_prefix = test_hash[:4]
            print(f"  Old hash prefix: {old_prefix}")
            print(f"  New hash prefix: {new_prefix}")

            # Try truncating password to 72 bytes like the function does
            truncated = password.encode("utf-8")[:72]
            print(f"  Password bytes (truncated): {len(truncated)} bytes")
        else:
            print("\n✓ Password VERIFIED!")

            # Check role restrictions
            if not user.is_active:
                print(f"❌ User is NOT ACTIVE")
            elif user.role == models.RoleEnum.NGO and not user.is_verified:
                print(f"❌ NGO not verified yet")
            elif user.role == models.RoleEnum.VOLUNTEER:
                v_status = (user.volunteer_status or "pending").lower()
                if v_status != "approved":
                    print(f"❌ Volunteer status is '{v_status}', not 'approved'")
                else:
                    print("✓ All checks passed! Login should succeed.")
            else:
                print("✓ All checks passed! Login should succeed.")

    finally:
        db.close()


if __name__ == "__main__":
    email = input("Enter email to test: ").strip()
    password = input("Enter password to test: ").strip()
    test_login(email, password)

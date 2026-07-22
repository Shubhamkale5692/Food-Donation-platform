import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Food Donation Platform", "backend"))

from app.infrastructure.database import SessionLocal
from app.domain.schemas import UserCreate
from app.domain.models import RoleEnum
from app.services.auth_service import create_user

def test_db():
    db = SessionLocal()
    try:
        user_in = UserCreate(email="test2@example.com", password="pwd", name="testname", role=RoleEnum.DONOR)
        create_user(db, user_in)
        print("Success!")
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_db()

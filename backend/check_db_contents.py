import asyncio
import os
from sqlalchemy import text
from app.core.database import SessionLocal

def check_db():
    db = SessionLocal()
    try:
        users = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
        donations = db.execute(text("SELECT COUNT(*) FROM donations")).scalar()
        print(f"Users: {users}")
        print(f"Donations: {donations}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_db()

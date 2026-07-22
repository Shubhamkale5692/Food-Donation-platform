import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.infrastructure.database import engine
from sqlalchemy import text

def add_columns():
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE donations ADD COLUMN IF NOT EXISTS task_type VARCHAR(20) DEFAULT 'pickup'"))
            conn.execute(text("ALTER TABLE donations ADD COLUMN IF NOT EXISTS distribution_status VARCHAR(20) DEFAULT 'pending'"))
            conn.execute(text("ALTER TABLE donations ADD COLUMN IF NOT EXISTS distribution_otp VARCHAR(10)"))
            print("Successfully added distribution columns to donations table.")
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    add_columns()

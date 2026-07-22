import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.infrastructure.database import engine
from sqlalchemy import text

def add_columns():
    with engine.begin() as conn:
        try:
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT \'pending\';'))
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lat FLOAT;'))
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lng FLOAT;'))
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS rating FLOAT DEFAULT 5.0;'))
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS completed_deliveries INTEGER DEFAULT 0;'))
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS volunteer_status VARCHAR DEFAULT \'pending\';'))
            
            conn.execute(text('ALTER TABLE donations ADD COLUMN IF NOT EXISTS volunteer_id UUID REFERENCES users(id);'))
            conn.execute(text('ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_status VARCHAR DEFAULT \'pending\';'))
            conn.execute(text('ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_code VARCHAR;'))
            conn.execute(text('ALTER TABLE donations ADD COLUMN IF NOT EXISTS otp_verified BOOLEAN DEFAULT FALSE;'))
            conn.execute(text('ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_time TIMESTAMP;'))
            conn.execute(text('ALTER TABLE donations ADD COLUMN IF NOT EXISTS delivery_time TIMESTAMP;'))
            conn.execute(text('ALTER TABLE donations ADD COLUMN IF NOT EXISTS ai_confidence_score FLOAT;'))
            
            # Add Volunteer features
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS ngo_id UUID REFERENCES users(id);'))
            conn.execute(text('ALTER TABLE donations ADD COLUMN IF NOT EXISTS assignment_time TIMESTAMP;'))
            conn.execute(text('ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_location VARCHAR;'))
            
            print("Successfully added columns.")
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    add_columns()

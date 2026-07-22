import sys
import os

# Ensure app is in Python path if run standalone
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.infrastructure.database import SessionLocal

def migrate():
    db = SessionLocal()
    try:
        print("Starting DB migration...")
        
        # 1. Temporarily drop default constraint and change column type to VARCHAR
        db.execute(text("ALTER TABLE donations ALTER COLUMN status DROP DEFAULT;"))
        db.execute(text("ALTER TABLE donations ALTER COLUMN status TYPE VARCHAR(50);"))
        print("Altered status to VARCHAR.")
        
        # 2. Update existing data to match new enum
        db.execute(text("UPDATE donations SET status='pending' WHERE status='Pending';"))
        db.execute(text("UPDATE donations SET status='accepted' WHERE status='Accepted' OR status='Claimed';"))
        db.execute(text("UPDATE donations SET status='assigned' WHERE status='Assigned';"))
        db.execute(text("UPDATE donations SET status='in_progress' WHERE status='Picked_Up' OR status='In-Transit';"))
        db.execute(text("UPDATE donations SET status='completed' WHERE status='Completed';"))
        db.execute(text("UPDATE donations SET status='cancelled' WHERE status='Cancelled';"))
        print("Updated existing records.")
        
        # 3. Drop old enum type
        db.execute(text("DROP TYPE IF EXISTS donationstatusenum;"))
        print("Dropped old enum.")
        
        # 4. Create new enum
        db.execute(text("CREATE TYPE donationstatusenum AS ENUM ('pending', 'accepted', 'assigned', 'in_progress', 'completed', 'cancelled');"))
        print("Created new enum.")
        
        # 5. Convert column back to ENUM using the new type
        db.execute(text("ALTER TABLE donations ALTER COLUMN status TYPE donationstatusenum USING status::donationstatusenum;"))
        db.execute(text("ALTER TABLE donations ALTER COLUMN status SET DEFAULT 'pending'::donationstatusenum;"))
        print("Altered back to ENUM.")
        
        # 6. Add Indexes
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_donations_status ON donations (status);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_donations_ngo_id ON donations (ngo_id);"))
        print("Indexes created.")
        
        db.commit()
        print("Migration complete!")
    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

import os
import sys
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

def main():
    # Use 127.0.0.1 instead of localhost to avoid IPv6 issues on some Windows setups
    db_url = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/foodbridge"
    )

    # Try to get from .env if available
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        print(f"Reading from {env_file}...")
        with open(env_file) as f:
            for line in f:
                if line.strip().startswith("DATABASE_URL"):
                    val = line.strip().split("=")[1].strip()
                    if val.startswith('"') or val.startswith("'"):
                         val = val[1:-1]
                    db_url = val.replace("db:5432", "127.0.0.1:5432")
                    break

    # Add app to path for any potential imports
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

    print(f"Connecting to: {db_url.split('@')[1] if '@' in db_url else '127.0.0.1'}")

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Find donations that are completed but miss total_duration
            query = text("""
                SELECT id, start_time, assignment_time, delivery_time 
                FROM donations 
                WHERE (status = 'completed' OR status = 'COMPLETED') 
                  AND total_duration IS NULL 
                  AND delivery_time IS NOT NULL
                  AND (start_time IS NOT NULL OR assignment_time IS NOT NULL)
            """)
            
            rows = conn.execute(query).fetchall()
            print(f"Found {len(rows)} completed donations missing total_duration that can be fixed.")
            
            updates = 0
            for row in rows:
                d_id, start_time, assign_time, delivery_time = row
                
                # Start reference
                start_ref = start_time or assign_time
                
                if start_ref and delivery_time:
                    # Handle timezone naive vs aware
                    s_ref = start_ref
                    d_time = delivery_time
                    if s_ref.tzinfo is None:
                        s_ref = s_ref.replace(tzinfo=timezone.utc)
                    if d_time.tzinfo is None:
                        d_time = d_time.replace(tzinfo=timezone.utc)
                    
                    # Calculate duration in minutes
                    duration = int((d_time - s_ref).total_seconds() / 60)
                    
                    # Sanity check: don't save negative duration or absurdly huge ones (> 7 days)
                    if 0 <= duration <= 10080:
                        conn.execute(
                            text("UPDATE donations SET total_duration = :dur WHERE id = :id"),
                            {"dur": duration, "id": d_id}
                        )
                        updates += 1
            
            conn.commit()
            print(f"SUCCESS: Updated {updates} donations.")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

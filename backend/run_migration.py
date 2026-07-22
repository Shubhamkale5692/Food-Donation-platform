"""
Run database migration for delivery timer columns.
Usage: python run_migration.py
"""

import os
import sys

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from sqlalchemy import create_engine, text


def main():
    from app.core.config import settings
    db_url = settings.SQLALCHEMY_DATABASE_URI

    print(f"Connecting to: {db_url.split('@')[1] if '@' in db_url else 'localhost'}")

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Add start_time column
            try:
                conn.execute(
                    text(
                        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS start_time TIMESTAMP"
                    )
                )
                print("✓ Added start_time column")
            except Exception as e:
                print(f"- start_time: {e}")

            # Add total_duration column
            try:
                conn.execute(
                    text(
                        "ALTER TABLE donations ADD IF NOT EXISTS total_duration INTEGER"
                    )
                )
                print("✓ Added total_duration column")
            except Exception as e:
                print(f"- total_duration: {e}")

            # Create indexes
            try:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_donations_start_time ON donations(start_time)"
                    )
                )
                print("✓ Created index on start_time")
            except Exception as e:
                print(f"- start_time index: {e}")

            try:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_donations_total_duration ON donations(total_duration)"
                    )
                )
                print("✓ Created index on total_duration")
            except Exception as e:
                print(f"- total_duration index: {e}")

            conn.commit()

            # Verify
            result = conn.execute(
                text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'donations' 
                  AND column_name IN ('start_time', 'total_duration')
                ORDER BY column_name
            """)
            )

            print("\nVerification:")
            for row in result:
                print(f"  - {row[0]}: {row[1]} ({row[2]})")

        print("\n✅ Migration complete!")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure PostgreSQL is running and accessible.")
        sys.exit(1)


if __name__ == "__main__":
    main()

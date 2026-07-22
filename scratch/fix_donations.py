
import os
import sys

# Database connection URL
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/foodbridge"

try:
    from sqlalchemy import create_engine, text
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # 1. Update status to 'ready_for_distribution' for all tested items that aren't distributed yet
        result = conn.execute(text("""
            UPDATE donations 
            SET status = 'ready_for_distribution', volunteer_id = NULL 
            WHERE decision IN ('distribute', 'urgent') 
              AND (status IS NULL OR status NOT IN ('distributed', 'assigned'));
        """))
        conn.commit()
        print(f"SUCCESS: Updated {result.rowcount} donations.")
except Exception as e:
    print(f"ERROR: {str(e)}")

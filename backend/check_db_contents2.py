from sqlalchemy import create_engine, text

SQLALCHEMY_DATABASE_URI = "postgresql://postgres:postgres@localhost/foodbridge"

def check_db():
    engine = create_engine(SQLALCHEMY_DATABASE_URI)
    try:
        with engine.connect() as conn:
            users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            donations = conn.execute(text("SELECT COUNT(*) FROM donations")).scalar()
            print(f"Users in DB: {users}")
            print(f"Donations in DB: {donations}")
            
            # Show a few users
            users_sample = conn.execute(text("SELECT id, name, role FROM users LIMIT 3")).fetchall()
            print(f"Users sample: {users_sample}")
            
            # Show a few donations
            donations_sample = conn.execute(text("SELECT id, status, ngo_id FROM donations LIMIT 3")).fetchall()
            print(f"Donations sample: {donations_sample}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()

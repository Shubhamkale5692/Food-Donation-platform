import psycopg2

passwords = ["postgres", "password", "root", "", "admin"]
conn = None
for pwd in passwords:
    try:
        conn = psycopg2.connect(host="localhost", user="postgres", password=pwd, dbname="foodbridge")
        print(f"Connected with password: {pwd}")
        break
    except Exception:
        pass

if not conn:
    print("Could not connect with any password.")
else:
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ngo_id UUID REFERENCES users(id);")
    cursor.execute("ALTER TABLE donations ADD COLUMN IF NOT EXISTS assignment_time TIMESTAMP;")
    cursor.execute("ALTER TABLE donations ADD COLUMN IF NOT EXISTS pickup_location VARCHAR;")
    conn.commit()
    print("Database columns added successfully.")

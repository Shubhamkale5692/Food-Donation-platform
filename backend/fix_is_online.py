import psycopg2

# Direct DB connection — no app imports needed
conn = psycopg2.connect(
    host="localhost",
    user="postgres",
    password="postgres",
    dbname="foodbridge"
)
conn.autocommit = False
cur = conn.cursor()

# Check if is_online exists
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='users' AND column_name='is_online';
""")
if cur.fetchone():
    print("Column 'is_online' already exists — skipping ALTER TABLE.")
else:
    cur.execute("ALTER TABLE users ADD COLUMN is_online BOOLEAN DEFAULT FALSE;")
    conn.commit()
    print("Column 'is_online' added successfully.")

# List all user columns for verification
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='users'
    ORDER BY ordinal_position;
""")
print("\nUsers table columns:")
for row in cur.fetchall():
    print(f"  {row[0]} ({row[1]})")

cur.close()
conn.close()
print("\nDone.")

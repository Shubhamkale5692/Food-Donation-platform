from fastapi.testclient import TestClient
import traceback

from app.main import app

client = TestClient(app)

def run():
    try:
        print("Testing Invalid Email...")
        response = client.post("/login", json={"email": "nonexistent@example.com", "password": "pass"})
        print(f"Status: {response.status_code}")
        print(f"Body: {response.json()}")
    except Exception as e:
        print("Exception caught:")
        traceback.print_exc()

if __name__ == "__main__":
    run()

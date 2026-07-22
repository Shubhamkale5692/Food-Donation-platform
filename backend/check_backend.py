from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def check_routes():
    routes = [r.path for r in app.routes]
    expected = [
        "/api/v1/admin/stats",
        "/api/v1/admin/system-donations",
        "/api/v1/ngo/stats",
        "/api/v1/ai/impact-insights"
    ]
    for e in expected:
        if e in routes:
            print(f"✓ Found route: {e}")
        else:
            print(f"✗ Missing route: {e}")

if __name__ == "__main__":
    try:
        check_routes()
        print("\nBackend diagnostic: SUCCESS")
    except Exception as e:
        print(f"\nBackend diagnostic: FAILED - {e}")

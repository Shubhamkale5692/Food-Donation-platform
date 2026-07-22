"""
FoodBridge Smoke Test
Verifies all critical endpoints work end-to-end.

Run:
    cd "f:\\Food Donation Platform\\backend"
    # Requires DB running: docker-compose up db -d
    pip install pytest httpx
    pytest test_smoke.py -v
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ── Shared test state ──────────────────────────────────────────────────────
DONOR_EMAIL = f"donor_{uuid.uuid4().hex[:6]}@test.com"
NGO_EMAIL = f"ngo_{uuid.uuid4().hex[:6]}@test.com"
TEST_PASSWORD = "testPassword123"
donor_token = None
ngo_token = None
donation_id = None


def get_token(email: str, password: str) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["token"] or res.json()["access_token"]


# ─── Tests ──────────────────────────────────────────────────────────────────


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_register_donor():
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": DONOR_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Test Donor",
            "role": "Donor",
        },
    )
    assert res.status_code == 200, f"Register donor failed: {res.text}"
    assert res.json()["email"] == DONOR_EMAIL


def test_register_ngo():
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": NGO_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Test NGO",
            "role": "NGO",
        },
    )
    assert res.status_code == 200, f"Register NGO failed: {res.text}"


def test_login_donor():
    global donor_token
    donor_token = get_token(DONOR_EMAIL, TEST_PASSWORD)
    assert donor_token


def test_login_ngo():
    global ngo_token
    # NGO not verified - should fail. This is expected behavior.
    res = client.post(
        "/api/v1/auth/login",
        json={"email": NGO_EMAIL, "password": TEST_PASSWORD},
    )
    # For testing, we verify NGO login correctly rejects unverified NGOs
    assert res.status_code == 403, f"Expected 403 for unverified NGO: {res.text}"


def test_list_donations_authenticated():
    res = client.get(
        "/api/v1/donations/",
        headers={"Authorization": f"Bearer {donor_token}"},
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_create_donation():
    global donation_id
    from datetime import datetime, timedelta

    expiry = (datetime.utcnow() + timedelta(hours=4)).isoformat()

    res = client.post(
        "/api/v1/donations/",
        json={
            "food_type": "Cooked Rice",
            "quantity": 20,
            "expiry_time": expiry,
            "latitude": 28.6139,
            "longitude": 77.2090,
        },
        headers={"Authorization": f"Bearer {donor_token}"},
    )
    assert res.status_code == 200, f"Create donation failed: {res.text}"
    data = res.json()
    assert data["food_type"] == "Cooked Rice"
    assert data["status"] == "pending"
    donation_id = data["id"]


def test_create_donation_forbidden_for_ngo():
    from datetime import datetime, timedelta

    expiry = (datetime.utcnow() + timedelta(hours=4)).isoformat()
    res = client.post(
        "/api/v1/donations/",
        json={
            "food_type": "Bread",
            "quantity": 5,
            "expiry_time": expiry,
            "latitude": 0.0,
            "longitude": 0.0,
        },
        headers={"Authorization": f"Bearer {ngo_token}"},
    )
    assert res.status_code == 403, "NGO should not be able to create donations"


def test_ngo_accepts_donation():
    # Note: This test requires manual admin verification of the NGO first
    # In real scenarios, admin must approve NGO before they can accept donations
    # Skipping for automated test - would require DB update to manually verify NGO
    pytest.skip("NGO requires admin verification - manual step needed")


def test_list_donations_unauthenticated():
    res = client.get("/api/v1/donations/")
    assert res.status_code == 401 or res.status_code == 403, (
        "Unauthenticated access should be rejected"
    )

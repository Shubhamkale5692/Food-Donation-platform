import requests
import uuid
import time
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000/api/v1"
DB_URL = "postgresql://postgres:postgres@localhost/foodbridge"

def approve_user_in_db(email, role):
    try:
        engine = create_engine(DB_URL)
        with engine.begin() as conn:
            if role == "ngo":
                conn.execute(text("UPDATE users SET is_verified = TRUE, is_active = TRUE WHERE email = :email"), {"email": email})
            elif role == "volunteer":
                conn.execute(text("UPDATE users SET volunteer_status = 'approved', is_active = TRUE WHERE email = :email"), {"email": email})
        print(f"✅ Database approval attempted for {role} ({email})")
    except Exception as e:
        print(f"⚠️ DB Approval failed for {email}: {e}")

def get_status(d):
    s = d.get('status')
    if isinstance(s, dict): return s.get('value')
    return s

def test_flow():
    test_pass = "password"
    
    # 1. Register/Login as Donor
    donor_email = f"donor_{uuid.uuid4().hex[:6]}@example.com"
    payload = {"email": donor_email, "password": test_pass, "name": "Test Donor", "role": "Donor"}
    requests.post(f"{BASE_URL}/auth/register", json=payload)
    res = requests.post(f"{BASE_URL}/login", json={"email": donor_email, "password": test_pass})
    donor_token = res.json().get("token") or res.json().get("access_token")
    donor_headers = {"Authorization": f"Bearer {donor_token}"}
    print("✅ Donor Logged In")

    # 2. Register/Login as NGO
    ngo_email = f"ngo_{uuid.uuid4().hex[:6]}@example.com"
    payload = {"email": ngo_email, "password": test_pass, "name": "Test NGO", "role": "NGO"}
    requests.post(f"{BASE_URL}/auth/register", json=payload)
    approve_user_in_db(ngo_email, "ngo")
    res = requests.post(f"{BASE_URL}/login", json={"email": ngo_email, "password": test_pass})
    ngo_data = res.json()
    if not ngo_data.get("success"):
        print(f"❌ NGO Login failed: {ngo_data}")
        return
    ngo_token = ngo_data.get("token") or ngo_data.get("access_token")
    ngo_headers = {"Authorization": f"Bearer {ngo_token}"}
    print("✅ NGO Logged In")

    # 3. Register/Login as Volunteer
    res = requests.get(f"{BASE_URL}/auth/ngos")
    ngos_list = res.json()
    my_ngo_id = None
    for n in ngos_list:
        if n["email"] == ngo_email:
            my_ngo_id = n["id"]
            break
            
    vol_email = f"vol_{uuid.uuid4().hex[:6]}@example.com"
    payload = {"email": vol_email, "password": test_pass, "name": "Test Volunteer", "role": "Volunteer", "ngo_id": my_ngo_id}
    requests.post(f"{BASE_URL}/auth/register", json=payload)
    approve_user_in_db(vol_email, "volunteer")
    res = requests.post(f"{BASE_URL}/login", json={"email": vol_email, "password": test_pass})
    vol_data = res.json()
    if not vol_data.get("success"):
        print(f"❌ Volunteer Login failed: {vol_data}")
        return
    vol_token = vol_data.get("token") or vol_data.get("access_token")
    vol_headers = {"Authorization": f"Bearer {vol_token}"}
    print("✅ Volunteer Logged In")

    # 4. Donor Creates Donation
    expiry = (datetime.now() + timedelta(hours=5)).isoformat()
    donation_payload = {
        "food_type": "Veg Meals", "quantity": 50, "pickup_address": "Donor Place",
        "latitude": 28.6139, "longitude": 77.2090, "expiry_time": expiry, "description": "Fresh meals"
    }
    res = requests.post(f"{BASE_URL}/donations/", json=donation_payload, headers=donor_headers)
    donation = res.json()
    donation_id = donation.get("id")
    print(f"✅ Donation Created: {donation_id} | Status: {get_status(donation)}")

    # 5. NGO Claims Donation
    requests.post(f"{BASE_URL}/donations/{donation_id}/claim", headers=ngo_headers)
    res = requests.get(f"{BASE_URL}/donations/{donation_id}", headers=ngo_headers)
    print(f"✅ Donation Claimed | Status: {get_status(res.json())}")

    # 6. NGO Fetches Available Volunteers
    res = requests.get(f"{BASE_URL}/volunteer/available", headers=ngo_headers)
    vols = res.json()
    print(f"✅ Available Volunteers Found: {len(vols)}")
    
    # 7. NGO Assigns Volunteer
    vol_id = None
    for v in (vols if isinstance(vols, list) else []):
        if v.get("email") == vol_email or v.get("name") == "Test Volunteer" or "Test Volunteer" in v.get("displayName", ""):
            vol_id = v["id"]
            break
    
    if not vol_id:
        print("❌ Volunteer not found in available list.")
        return
        
    requests.post(f"{BASE_URL}/donations/{donation_id}/assign-volunteer?volunteer_id={vol_id}", headers=ngo_headers)
    res = requests.get(f"{BASE_URL}/donations/{donation_id}", headers=ngo_headers)
    print(f"✅ Volunteer Assigned | Status: {get_status(res.json())}")

    # 8. Volunteer Verifies assigned donation
    res = requests.get(f"{BASE_URL}/volunteer/my-deliveries", headers=vol_headers)
    found = any(str(d.get("id")) == str(donation_id) for d in (res.json() if isinstance(res.json(), list) else []))
    print(f"✅ Volunteer Receipt: {'Found' if found else 'NOT Found'}")

    # 9. Volunteer Generates and Verifies OTP (Simulate Pick Up)
    requests.post(f"{BASE_URL}/donations/{donation_id}/generate-otp", headers=vol_headers)
    requests.post(f"{BASE_URL}/donations/{donation_id}/verify-otp", json={"otp": "123456"}, headers=vol_headers)
    res = requests.get(f"{BASE_URL}/donations/{donation_id}", headers=vol_headers)
    d_status = get_status(res.json())
    print(f"✅ OTP Verified | Status: {d_status}")

    # 10. NGO checks Delivery Tracking
    res = requests.get(f"{BASE_URL}/ngo/delivery-tracking", headers=ngo_headers)
    tracking = res.json()
    found_tracking = any(str(d.get("donation_id")) == str(donation_id) for d in (tracking if isinstance(tracking, list) else []))
    print(f"✅ NGO Tracking: {'Found' if found_tracking else 'NOT Found'}")

    if found_tracking and d_status == "picked_up":
        print("\n🏁 FINAL RESULT: ALL FLOWS VERIFIED SUCCESSFULLY!")
    else:
        print("\n❌ FINAL RESULT: Flow verification FAILED.")

if __name__ == "__main__":
    test_flow()

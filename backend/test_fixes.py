import httpx
import time

API_URL = "http://localhost:8000/api/v1"

def print_step(msg):
    print(f"\n[{msg}]")

def main():
    try:
        # Step 1: Admin Login (assume default admin exists, or we register one)
        client = httpx.Client()
        
        # Create Admin
        print_step("Creating test Admin")
        admin_data = {"email": f"test_admin_{int(time.time())}@example.com", "password": "password", "name": "Admin", "role": "Admin"}
        r = client.post(f"{API_URL}/auth/register", json=admin_data)
        if r.status_code == 400:
            print("Admin already exists, proceeding...")
        
        # Test Admin Login 1
        print_step("Admin Login 1")
        r = client.post(f"{API_URL}/auth/login", json={"email": admin_data["email"], "password": admin_data["password"]})
        assert r.status_code == 200, f"Admin Login failed: {r.text}"
        admin_token = r.json()["access_token"]
        
        # Test Admin Logout
        print_step("Admin Logout")
        r = client.post(f"{API_URL}/auth/logout", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, f"Admin Logout failed: {r.text}"
        
        # Test Admin Login 2 (Should not be blocked)
        print_step("Admin Login 2 (Should not be blocked)")
        r = client.post(f"{API_URL}/auth/login", json={"email": admin_data["email"], "password": admin_data["password"]})
        assert r.status_code == 200, f"Multiple Admin Login blocked!: {r.text}"
        
        # Step 2: Create NGO and Approve it
        print_step("Creating NGO")
        ngo_email = f"ngo_{int(time.time())}@example.com"
        r = client.post(f"{API_URL}/auth/register", json={"email": ngo_email, "password": "password", "name": "NGO", "role": "NGO"})
        ngo_id = r.json()["id"]
        
        # Admin approves NGO
        print_step("Admin approves NGO")
        r = client.post(f"{API_URL}/admin/approve-ngo/{ngo_id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, f"Failed to approve NGO: {r.text}"
        
        # Step 3: NGO Login to get token
        print_step("NGO Login")
        r = client.post(f"{API_URL}/auth/login", json={"email": ngo_email, "password": "password"})
        ngo_token = r.json()["access_token"]
        
        # Step 4: Create Volunteer linked to NGO
        print_step("Volunteer registers (Linked to NGO)")
        vol_email = f"vol_{int(time.time())}@example.com"
        r = client.post(f"{API_URL}/auth/register", json={"email": vol_email, "password": "password", "name": "Volunteer", "role": "Volunteer", "ngo_id": ngo_id})
        vol_id = r.json()["id"]
        
        # Step 5: Volunteer Login (Should be blocked)
        print_step("Volunteer Login 1 (Should be blocked - Pending)")
        r = client.post(f"{API_URL}/auth/login", json={"email": vol_email, "password": "password"})
        assert r.status_code == 403, "Volunteer logged in while pending!"
        print(f"Volunteer properly blocked: {r.json()['detail']}")
        
        # Step 6: NGO Checks pending volunteers
        print_step("NGO checks pending volunteers")
        r = client.get(f"{API_URL}/volunteer/pending", headers={"Authorization": f"Bearer {ngo_token}"})
        pending = r.json()
        assert len(pending) > 0, "No pending volunteers found for NGO"
        assert pending[0]["id"] == vol_id, "Pending volunteer ID mismatch"
        
        # Step 7: NGO Approves volunteer
        print_step("NGO Approves Volunteer")
        r = client.post(f"{API_URL}/volunteer/approve/{vol_id}", headers={"Authorization": f"Bearer {ngo_token}"})
        assert r.status_code == 200, f"Approve failed: {r.text}"
        
        # Step 8: Volunteer Login 2 (Should succeed)
        print_step("Volunteer Login 2 (Should succeed)")
        r = client.post(f"{API_URL}/auth/login", json={"email": vol_email, "password": "password"})
        assert r.status_code == 200, f"Approved volunteer login failed: {r.text}"
        
        print("\n✅ All Tests Passed Successfully!")

    except Exception as e:
        print(f"\n❌ Test Failed: {e}")

if __name__ == "__main__":
    main()

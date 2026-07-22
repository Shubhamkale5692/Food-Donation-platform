import urllib.request
import json
import uuid

# Generate random unique email
email = f"testuser_{uuid.uuid4().hex[:6]}@example.com"
password = "TestPassword123!"

def hit_api(endpoint, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f'http://localhost:8000/api/v1{endpoint}', data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as f:
            print(f"[{endpoint}] Success:", f.read().decode('utf-8'))
            return True
    except urllib.error.HTTPError as e:
        print(f"[{endpoint}] HTTP Error:", e.code)
        try:
            print(f"[{endpoint}] Error Body:", e.read().decode('utf-8'))
        except:
            print(f"[{endpoint}] Could not read body")
        return False
    except urllib.error.URLError as e:
        print(f"[{endpoint}] URL Error (Connection Refused?):", e.reason)
        return False

print("--- Testing Registration ---")
reg_payload = {"email": email, "password": password, "name": "Test User", "role": "Donor"}
success = hit_api("/auth/register", reg_payload)

print("\n--- Testing Login ---")
login_payload = {"email": email, "password": password}
hit_api("/login", login_payload)

print("\n--- Testing Login with old user ---")
hit_api("/login", {"email": "test@test.com", "password": "123"})

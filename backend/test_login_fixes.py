import urllib.request
import urllib.error
import urllib.parse
import json
import time

API_URL = "http://localhost:8000"
API_V1_URL = "http://localhost:8000/api/v1"

def print_step(msg):
    print(f"\n[{msg}]")

def post_json(url, data):
    req = urllib.request.Request(url, method="POST")
    req.add_header('Content-Type', 'application/json')
    data_bytes = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req, data=data_bytes) as response:
            body = response.read().decode('utf-8')
            try:
                return response.status, json.loads(body)
            except json.JSONDecodeError:
                return response.status, {"raw_body": body}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"raw_body": body}
    except Exception as e:
        print(f"Connection error to {url}: {e}")
        return 0, {}

def main():
    try:
        # 1. Test invalid email
        print_step("Testing Invalid Email")
        status, data = post_json(f"{API_URL}/login", {"email": "nonexistent@example.com", "password": "pass"})
        assert status == 200, f"Invalid email should return 200, got {status}: {data}"
        assert data.get("success") is False, f"Unexpected success flag: {data}"
        assert data.get("message") == "User not found", f"Unexpected message: {data}"
        print("✅ Invalid email check passed")
        
        # 2. Test Invalid password
        print_step("Testing Invalid Password")
        user_email = f"test_login_{int(time.time())}@example.com"
        status, data = post_json(f"{API_V1_URL}/auth/register", {"email": user_email, "password": "correct_password", "name": "User", "role": "Donor"})
        assert status == 200, f"Failed to register user: {data}"
        
        status, data = post_json(f"{API_URL}/login", {"email": user_email, "password": "wrong_password"})
        assert status == 200, f"Invalid password should return 200, got {status}: {data}"
        assert data.get("success") is False, f"Unexpected success flag: {data}"
        assert data.get("message") == "Incorrect password", f"Unexpected message: {data}"
        print("✅ Invalid password check passed")
        
        # 3. Test Successful Login (bcrypt)
        print_step("Testing Successful Login (Hashed Password)")
        status, data = post_json(f"{API_URL}/login", {"email": user_email, "password": "correct_password"})
        assert status == 200, f"Valid login should return 200, got {status}: {data}"
        assert "access_token" in data, "Access token missing"
        print("✅ Successful login passed")
        
        print("\n✅ All Login Tests Passed Successfully!")

    except Exception as e:
        print(f"\n❌ Test Failed: {e}")

if __name__ == "__main__":
    main()

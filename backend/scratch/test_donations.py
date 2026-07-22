
import requests
import sys

URL = "http://localhost:8000/api/v1/donations/"

try:
    print(f"Testing GET {URL}...")
    # NOTE: This might fail if auth is required, but we want to see the error type (401 vs 500)
    r = requests.get(URL, timeout=5)
    print(f"Status: {r.status_code}")
    if r.status_code == 500:
        print("Backend is throwing 500!")
        try:
            print(f"Error detail: {r.json().get('detail', 'No detail')}")
        except:
            print("Could not parse error JSON.")
    else:
        print(f"Response: {r.text[:200]}...")
except Exception as e:
    print(f"Connection failed: {e}")

import urllib.request
import json

data = {
    "name": "Test Long Pass",
    "email": "testlongpass@example.com",
    "password": "a" * 100,
    "role": "Donor"
}

req = urllib.request.Request(
    "http://localhost:8000/api/v1/auth/register",
    data=json.dumps(data).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req) as f:
        print("Registration response:", f.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("Registration HTTP Error:", e.code, e.read().decode('utf-8'))

login_data = {
    "email": "testlongpass@example.com",
    "password": "a" * 100
}

req_login = urllib.request.Request(
    "http://localhost:8000/api/v1/auth/login",
    data=json.dumps(login_data).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req_login) as f:
        print("Login response:", f.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("Login HTTP Error:", e.code, e.read().decode('utf-8'))

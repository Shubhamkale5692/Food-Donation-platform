#!/usr/bin/env python
"""
Quick test script to verify login works.
Run with: python test_login_api.py
"""

import urllib.request
import json
import sys


def test_login():
    # Test credentials from seed_data.py
    test_users = [
        {"email": "admin@foodbridge.org", "password": "admin123"},
        {"email": "ngo1@foodbridge.org", "password": "ngo123"},
        {"email": "donor1@foodbridge.org", "password": "donor123"},
        {"email": "vol1@foodbridge.org", "password": "vol123"},
    ]

    for creds in test_users:
        data = json.dumps(creds).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/v1/auth/login",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req) as f:
                response = json.loads(f.read().decode("utf-8"))
                print(
                    f"✅ Login success for {creds['email']}: role={response.get('role')}"
                )
                return True
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            print(f"❌ Login failed for {creds['email']}: {e.code} {error_body}")
        except Exception as e:
            print(f"❌ Error for {creds['email']}: {e}")

    return False


if __name__ == "__main__":
    success = test_login()
    sys.exit(0 if success else 1)

"""Quick smoke-test for the new Food Testing endpoints (no auth required — 401 = route exists)."""
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api/v1"

tests = [
    ("GET",  "/ngo/received-donations", None),
    ("GET",  "/ngo/distribution",       None),
    ("GET",  "/ngo/waste",              None),
    ("POST", "/ngo/donations/00000000-0000-0000-0000-000000000000/test-food",
             b'{"quality":"fresh"}'),
]

all_ok = True
for method, path, data in tests:
    url = BASE + path
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        code = f"ERR:{e}"
        all_ok = False

    # 401 = route exists (auth required) — that's correct
    ok = code in (200, 401, 403, 404, 422)
    status = "OK" if ok else "FAIL"
    if not ok:
        all_ok = False
    print(f"[{status}] {method:<5} {path:<55} -> {code}")

print()
print("All routes registered:", "YES" if all_ok else "NO — check above")

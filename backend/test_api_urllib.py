import urllib.request
import urllib.error

url = "http://localhost:8000/api/v1/donations/?skip=0&limit=200"
try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        html = response.read()
        print(f"Status: {response.status}")
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code} {e.reason}")
    print(e.read().decode())
except urllib.error.URLError as e:
    print(f"URLError: {e.reason}")

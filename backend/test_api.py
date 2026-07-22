import urllib.error
import urllib.request

BASE_URL = "http://localhost:8000/api/v1"


def main() -> None:
    # If this returns 401, route is healthy but auth is required.
    # If it returns 500, backend route handling is broken.
    url = f"{BASE_URL}/donations/?skip=0&limit=200"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(f"Status: {response.status}")
            print(f"Body: {body}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Status: {exc.code}")
        print(f"Body: {body}")
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}")


if __name__ == "__main__":
    main()

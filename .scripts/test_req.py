import urllib.request
import json
import traceback

data = json.dumps({'email': 'test@test.com', 'password': '123'}).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/login', data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as f:
        print("Success:", f.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    try:
        err_body = e.read().decode('utf-8')
        print(err_body)
    except Exception as e2:
        print("Could not read error body:", e2)
except Exception as e:
    print("Other Error:", traceback.format_exc())

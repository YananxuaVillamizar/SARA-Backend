import urllib.request
import urllib.error
import json

BASE_URL = "http://localhost:8000"

# 1. Login to get token and id
login_payload = {
    "email": "esperanzatorres@unipamplona.edu.co",
    "password": "12345678"
}

try:
    print("Testing /auth/login...")
    req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps(login_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as response:
        login_data = json.loads(response.read().decode('utf-8'))
        token = login_data["access_token"]
        docente_id = login_data["id"]
        print(f"Login success! Token: {token[:10]}... ID: {docente_id}")

    # 2. Get docente stats
    print("Testing /dashboard/docente-stats...")
    req_stats = urllib.request.Request(
        f"{BASE_URL}/dashboard/docente-stats/{docente_id}",
        headers={"Authorization": f"Bearer {token}"},
        method='GET'
    )
    with urllib.request.urlopen(req_stats) as response_stats:
        stats = json.loads(response_stats.read().decode('utf-8'))
        print("Docente stats retrieved successfully:")
        print(json.dumps(stats, indent=2))
except Exception as e:
    print("Error during API request:", e)
    if hasattr(e, 'read'):
        print("Response detail:", e.read().decode('utf-8'))

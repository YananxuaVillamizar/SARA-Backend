import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from app.main import app

def main():
    client = TestClient(app)
    print("Testing GET /admin/horarios...")
    try:
        response = client.get("/admin/horarios")
        print("Status Code:", response.status_code)
        if response.status_code == 200:
            print("Successfully retrieved horarios!")
            horarios = response.json()
            print(f"Total horarios: {len(horarios)}")
            if horarios:
                print("First hor:", horarios[0])
        else:
            print("Error details:", response.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()

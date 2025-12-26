from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_routes():
    print("Testing GET /jobs/abc123")
    response = client.get("/jobs/abc123")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    print("\nTesting GET /jobs/submit")
    response = client.get("/jobs/submit")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    print("\nTesting POST /jobs/submit (empty body)")
    response = client.post("/jobs/submit", json={})
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    test_routes()

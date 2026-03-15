from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "sentinel"
    assert data["version"] == "0.1.0"


def test_list_accounts():
    response = client.get("/api/accounts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

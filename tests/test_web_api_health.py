from gamepulse.web_api.app import app
from fastapi.testclient import TestClient


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

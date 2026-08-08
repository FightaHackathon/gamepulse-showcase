from fastapi.testclient import TestClient

from api.service import app as vercel_api_app


def test_vercel_api_service_accepts_stripped_and_unstripped_api_health_paths():
    client = TestClient(vercel_api_app)

    stripped = client.get("/health")
    unstripped = client.get("/api/health")

    assert stripped.status_code == 200
    assert stripped.json() == {"status": "ok"}
    assert unstripped.status_code == 200
    assert unstripped.json() == {"status": "ok"}

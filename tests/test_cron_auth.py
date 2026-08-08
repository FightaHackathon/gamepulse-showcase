from fastapi.testclient import TestClient

from gamepulse.services.snapshot_refresh import RefreshReport
from gamepulse.web_api.app import app
from gamepulse.web_api.routes import jobs


def test_refresh_job_requires_matching_bearer_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    monkeypatch.setattr(
        jobs,
        "run_refresh",
        lambda settings: RefreshReport(
            status="success",
            games_considered=2,
            metrics_written=4,
            provider_runs=(),
        ),
    )

    client = TestClient(app)

    assert client.get("/api/jobs/refresh").status_code == 401
    assert client.get(
        "/api/jobs/refresh",
        headers={"Authorization": "Bearer wrong"},
    ).status_code == 401

    response = client.get(
        "/api/jobs/refresh",
        headers={"Authorization": "Bearer test-cron-secret"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "games_considered": 2,
        "metrics_written": 4,
        "provider_runs": [],
    }

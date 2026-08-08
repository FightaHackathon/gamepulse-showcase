from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from gamepulse.db.models import Base, ProviderRunModel
from gamepulse.web_api.app import app
from gamepulse.web_api.dependencies import get_db_session


NOW = datetime.now(timezone.utc)


def test_source_status_reports_latest_health_and_freshness():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all(
        [
            ProviderRunModel(
                provider_name="Steam Web API",
                started_at=NOW - timedelta(minutes=10),
                finished_at=NOW - timedelta(minutes=9),
                status="success",
                error_text=None,
                metrics_written=25,
            ),
            ProviderRunModel(
                provider_name="TwitchTracker",
                started_at=NOW - timedelta(minutes=8),
                finished_at=NOW - timedelta(minutes=7),
                status="failure",
                error_text="upstream unavailable",
                metrics_written=0,
            ),
            ProviderRunModel(
                provider_name="SteamSpy",
                started_at=NOW - timedelta(hours=72),
                finished_at=NOW - timedelta(hours=71),
                status="success",
                error_text=None,
                metrics_written=12,
            ),
        ]
    )
    session.commit()

    def override_session():
        yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        response = TestClient(app).get("/api/status/sources")
        assert response.status_code == 200
        sources = {item["provider_name"]: item for item in response.json()["sources"]}

        assert sources["Steam Web API"]["state"] == "healthy"
        assert sources["Steam Web API"]["freshness"] == "fresh"
        assert sources["Steam Web API"]["latest_success_at"]

        assert sources["TwitchTracker"]["state"] == "error"
        assert sources["TwitchTracker"]["latest_failure_at"]
        assert sources["TwitchTracker"]["last_error"] == "upstream unavailable"

        assert sources["SteamSpy"]["state"] == "stale"
        assert sources["SteamSpy"]["freshness"] == "stale"
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()

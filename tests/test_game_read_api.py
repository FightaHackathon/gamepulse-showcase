from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gamepulse.db.models import (
    Base,
    GameGenreModel,
    GameModel,
    GameTagModel,
    SteamSnapshotModel,
    SteamSpySnapshotModel,
    StreamingSnapshotModel,
)
from gamepulse.web_api.app import app
from gamepulse.web_api.dependencies import get_db_session


NOW = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)


def test_game_detail_and_history_are_served_from_cached_database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        GameModel(
            steam_app_id=10,
            name="Example Game",
            release_date="2026-07-01",
            price_usd=19.99,
            review_score=0.91,
            total_reviews=12000,
            header_image_url="https://example.test/header.jpg",
            short_description="A compact test game.",
        )
    )
    session.add_all(
        [
            GameTagModel(steam_app_id=10, value="Co-op"),
            GameGenreModel(steam_app_id=10, value="Action"),
            SteamSnapshotModel(
                steam_app_id=10,
                metric="current_players",
                value_numeric=1200,
                value_text=None,
                source_name="Steam Web API",
                source_mode="public_api",
                observed_at=NOW - timedelta(hours=2),
                confidence="high",
                source_url="https://api.steampowered.com/example",
            ),
            SteamSnapshotModel(
                steam_app_id=10,
                metric="current_players",
                value_numeric=1500,
                value_text=None,
                source_name="Steam Web API",
                source_mode="public_api",
                observed_at=NOW,
                confidence="high",
                source_url="https://api.steampowered.com/example",
            ),
            StreamingSnapshotModel(
                steam_app_id=10,
                external_game_id="Example Game",
                game_name="Example Game",
                metric="average_viewers_30d",
                value_numeric=450,
                value_text=None,
                source_name="TwitchTracker",
                source_mode="public_30d_summary",
                observed_at=NOW,
                confidence="medium",
                source_url="https://twitchtracker.com/example",
            ),
            SteamSpySnapshotModel(
                steam_app_id=10,
                owners_low=100_000,
                owners_high=200_000,
                source_name="SteamSpy",
                source_mode="public_estimate",
                observed_at=NOW,
                confidence="low",
                source_url="https://steamspy.com/example",
            ),
        ]
    )
    session.commit()

    def override_session():
        yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        client = TestClient(app)
        response = client.get("/api/games/10")
        assert response.status_code == 200
        body = response.json()
        assert body["steam_app_id"] == 10
        assert body["name"] == "Example Game"
        assert body["header_image_url"] == "https://example.test/header.jpg"
        assert body["steam_store_url"] == "https://store.steampowered.com/app/10"
        assert body["tags"] == ["Co-op"]
        assert body["genres"] == ["Action"]

        metrics = {item["metric"]: item for item in body["metrics"]}
        assert metrics["current_players"]["value_numeric"] == 1500
        assert metrics["average_viewers_30d"]["value_numeric"] == 450
        assert metrics["owners_low_estimate"]["value_numeric"] == 100_000
        assert metrics["owners_high_estimate"]["value_numeric"] == 200_000
        for metric in metrics.values():
            assert metric["source_name"]
            assert metric["source_mode"]
            assert metric["observed_at"]
            assert metric["confidence"]
            assert metric["signal_type"] in {"steam", "streaming", "steamspy"}

        history = client.get("/api/games/10/history", params={"metric": "current_players"})
        assert history.status_code == 200
        points = history.json()["points"]
        assert [point["value_numeric"] for point in points] == [1200, 1500]

        assert client.get("/api/games/999999").status_code == 404
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()

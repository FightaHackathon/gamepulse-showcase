from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from gamepulse.db.models import (
    Base,
    GameGenreModel,
    GameModel,
    GameTagModel,
    ReviewModel,
    SteamSnapshotModel,
    SteamSpySnapshotModel,
    StreamingSnapshotModel,
)
from gamepulse.web_api.app import app
from gamepulse.web_api.dependencies import get_db_session
from gamepulse.web_api.routes import games
from gamepulse.providers.contracts import ProviderMetric


NOW = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)


def test_game_detail_and_history_are_served_from_cached_database():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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


def test_game_detail_uses_artifact_metrics_only_when_snapshot_value_is_missing(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(GameModel(steam_app_id=10, name="Example Game"))
    session.add(
        SteamSnapshotModel(
            steam_app_id=10,
            metric="current_players",
            value_numeric=1500,
            source_name="Steam Web API",
            source_mode="public_api",
            observed_at=NOW,
            confidence="high",
        )
    )
    session.commit()

    class ArtifactRow:
        observed_at = NOW - timedelta(days=7)
        source_name = "Bundled artifact"
        source_mode = "derived_multi_signal"
        confidence = "medium"
        components = {"current_players": 9000, "peak_ccu": 12000}

    class StreamingArtifactRow(ArtifactRow):
        components = {"average_viewers_30d": 640}

    monkeypatch.setattr(
        games,
        "load_trend_artifact",
        lambda: {(10, "player"): ArtifactRow(), (10, "streamer"): StreamingArtifactRow()},
    )

    def override_session():
        yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        body = TestClient(app).get("/api/games/10").json()
        metrics = {item["metric"]: item for item in body["metrics"]}

        assert metrics["current_players"]["value_numeric"] == 1500
        assert metrics["current_players"]["source_name"] == "Steam Web API"
        assert metrics["peak_ccu"]["value_numeric"] == 12000
        assert metrics["peak_ccu"]["source_mode"] == "derived_multi_signal"
        assert metrics["average_viewers_30d"]["value_numeric"] == 640

        history = TestClient(app).get("/api/games/10/history", params={"metric": "average_viewers_30d"})
        assert history.json()["points"] == []
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_game_detail_returns_review_counts_and_ranked_positive_negative_excerpts():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        GameModel(
            steam_app_id=10,
            name="Example Game",
            positive_reviews=90,
            negative_reviews=30,
            total_reviews=120,
            review_score=0.75,
        )
    )
    session.add_all(
        [
            ReviewModel(review_id="p-low", steam_app_id=10, review_text="Positive but less helpful", recommended=True, helpful_votes=2, created_at_unix=100, source_mode="public_store_api", source_url="https://store.steampowered.com/appreviews/10?language=english"),
            ReviewModel(review_id="p-high", steam_app_id=10, review_text="Most positive helpful review", recommended=True, helpful_votes=10, created_at_unix=90, source_mode="public_store_api", source_url="https://store.steampowered.com/appreviews/10?language=english"),
            ReviewModel(review_id="p-new", steam_app_id=10, review_text="New positive review", recommended=True, helpful_votes=10, created_at_unix=110, source_mode="public_store_api", source_url="https://store.steampowered.com/appreviews/10?language=english"),
            ReviewModel(review_id="p-four", steam_app_id=10, review_text="Fourth positive review", recommended=True, helpful_votes=1, created_at_unix=120, source_mode="public_store_api", source_url="https://store.steampowered.com/appreviews/10?language=english"),
            ReviewModel(review_id="p-other-language", steam_app_id=10, review_text="Nicht englische Bewertung", recommended=True, helpful_votes=999, created_at_unix=130, source_mode="public_store_api", source_url="https://store.steampowered.com/appreviews/10?language=german"),
            ReviewModel(review_id="n-low", steam_app_id=10, review_text="Negative but less helpful", recommended=False, helpful_votes=1, created_at_unix=100, source_mode="public_store_api", source_url="https://store.steampowered.com/appreviews/10?language=english"),
            ReviewModel(review_id="n-high", steam_app_id=10, review_text="Most negative helpful review", recommended=False, helpful_votes=8, created_at_unix=90, source_mode="public_store_api", source_url="https://store.steampowered.com/appreviews/10?language=english"),
            ReviewModel(review_id="n-new", steam_app_id=10, review_text="New negative review", recommended=False, helpful_votes=8, created_at_unix=110, source_mode="public_store_api", source_url="https://store.steampowered.com/appreviews/10?language=english"),
            ReviewModel(review_id="n-four", steam_app_id=10, review_text="Fourth negative review", recommended=False, helpful_votes=1, created_at_unix=120, source_mode="public_store_api", source_url="https://store.steampowered.com/appreviews/10?language=english"),
            ReviewModel(review_id="unknown", steam_app_id=10, review_text="Unknown sentiment", recommended=None, helpful_votes=100, created_at_unix=200, source_mode="public_store_api", source_url="https://store.steampowered.com/appreviews/10?language=english"),
        ]
    )
    session.commit()

    def override_session():
        yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        body = TestClient(app).get("/api/games/10").json()
        assert body["positive_reviews"] == 90
        assert body["negative_reviews"] == 30
        excerpts = body["review_excerpts"]
        assert [item["text"] for item in excerpts["positive"]] == [
            "New positive review",
            "Most positive helpful review",
            "Positive but less helpful",
        ]
        assert [item["text"] for item in excerpts["negative"]] == [
            "New negative review",
            "Most negative helpful review",
            "Fourth negative review",
        ]
        assert "Fourth positive review" not in str(excerpts)
        assert "Nicht englische Bewertung" not in str(excerpts)
        assert "Unknown sentiment" not in str(excerpts)
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_game_detail_does_not_fabricate_metrics_without_direct_artifact_components(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(GameModel(steam_app_id=10, name="Example Game", peak_ccu=9999))
    session.commit()

    class ArtifactRow:
        observed_at = NOW
        source_name = "Bundled artifact"
        source_mode = "derived_multi_signal"
        confidence = "medium"
        components = {"review_score": 91}

    monkeypatch.setattr(games, "load_trend_artifact", lambda: {(10, "player"): ArtifactRow()})

    def override_session():
        yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        body = TestClient(app).get("/api/games/10").json()
        assert {item["metric"] for item in body["metrics"]}.isdisjoint(
            {"current_players", "peak_ccu", "average_viewers_30d"}
        )
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_selected_game_refresh_is_bounded_and_reports_provider_fallback(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(GameModel(steam_app_id=20, name="Selected Game"))
    session.commit()

    class FakeSteam:
        provider_name = "Steam Web API"
        signal_type = "steam"

        def __init__(self, **_kwargs):
            pass

        def fetch(self, game):
            return [ProviderMetric("current_players", 321, NOW, self.provider_name, "public_api", "high")]

    class FailingStreaming:
        provider_name = "TwitchTracker"
        signal_type = "streaming"

        def __init__(self, **_kwargs):
            pass

        def fetch(self, game):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(games, "SteamCurrentPlayersProvider", FakeSteam)
    monkeypatch.setattr(games, "TwitchTrackerProvider", FailingStreaming)
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite://")

    def override_session():
        yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        body = TestClient(app).get("/api/games/20?refresh=true").json()
        metrics = {item["metric"]: item for item in body["metrics"]}
        assert metrics["current_players"]["value_numeric"] == 321
        assert body["refresh_status"] == "partial_success"
        assert [item["provider_name"] for item in body["refresh_providers"]] == ["Steam Web API", "TwitchTracker"]
        assert body["refresh_providers"][1]["status"] == "failure"
        assert "provider unavailable" in body["refresh_providers"][1]["error"]
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()

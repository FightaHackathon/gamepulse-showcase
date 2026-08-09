from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from gamepulse.db.models import Base, GameGenreModel, GameModel, GameTagModel, SteamSnapshotModel, StreamingSnapshotModel, TrendScoreModel
from gamepulse.providers.steam import PlayerLibrary, parse_steam_profile
from gamepulse.web_api.app import app
from gamepulse.web_api.dependencies import get_db_session
from gamepulse.web_api.routes.player import get_player_session
from gamepulse.web_api.routes import player
from gamepulse.web_api.routes import fusion


@pytest.fixture
def client(monkeypatch):
    class PublicSteamProvider:
        def __init__(self, api_key):
            self.api_key = api_key

        def resolve_profile(self, profile):
            steam_id, vanity = parse_steam_profile(profile)
            return steam_id or vanity or "76561198000000000"

        def get_library(self, steam_id):
            return PlayerLibrary(steam_id, (), "Public Steam games page", True)

    monkeypatch.setattr(player, "SteamProvider", PublicSteamProvider)
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    observed_at = datetime(2026, 8, 8, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add_all(
            [
                GameModel(
                    steam_app_id=10,
                    name="Signal Drift",
                    price_usd=14.99,
                    peak_ccu=1200,
                    total_reviews=900,
                    review_score=0.92,
                    header_image_url="https://example.test/signal.jpg",
                    short_description="A cooperative salvage game.",
                ),
                GameModel(
                    steam_app_id=20,
                    name="Night Circuit",
                    price_usd=19.99,
                    peak_ccu=700,
                    total_reviews=450,
                    review_score=0.78,
                    header_image_url="https://example.test/night.jpg",
                    short_description="A tactical racing game.",
                ),
            ]
        )
        session.add_all(
            [
                GameTagModel(steam_app_id=10, value="Co-op"),
                GameTagModel(steam_app_id=20, value="Racing"),
                GameGenreModel(steam_app_id=10, value="Action"),
                GameGenreModel(steam_app_id=20, value="Racing"),
                SteamSnapshotModel(
                    steam_app_id=10,
                    metric="current_players",
                    value_numeric=800,
                    source_name="fixture",
                    source_mode="cached",
                    observed_at=observed_at,
                    confidence="medium",
                ),
                SteamSnapshotModel(
                    steam_app_id=20,
                    metric="current_players",
                    value_numeric=300,
                    source_name="fixture",
                    source_mode="cached",
                    observed_at=observed_at,
                    confidence="medium",
                ),
                StreamingSnapshotModel(
                    steam_app_id=10,
                    game_name="Signal Drift",
                    metric="average_viewers_30d",
                    value_numeric=4200,
                    source_name="fixture",
                    source_mode="historical_snapshot",
                    observed_at=observed_at,
                    confidence="medium",
                ),
                StreamingSnapshotModel(
                    steam_app_id=10,
                    game_name="Signal Drift",
                    metric="channel_count",
                    value_numeric=80,
                    source_name="fixture",
                    source_mode="historical_snapshot",
                    observed_at=observed_at,
                    confidence="medium",
                ),
                TrendScoreModel(
                    steam_app_id=10,
                    audience="player",
                    score=0.72,
                    components={"growth": 0.8},
                    observed_at=observed_at,
                    confidence="medium",
                ),
                TrendScoreModel(
                    steam_app_id=10,
                    audience="developer",
                    score=72.0,
                    components={
                        "market_demand": 64.0,
                        "genre_demand": 58.0,
                        "genre_competition": 22.0,
                        "review_sentiment": 92.0,
                        "opportunity_gap": 45.0,
                    },
                    observed_at=observed_at,
                    confidence="medium",
                ),
            ]
        )
        session.commit()

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_player_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_player_analyze_returns_weighted_explainable_recommendations(client):
    response = client.post(
        "/api/player/analyze",
        json={"steam_profile_url": "https://steamcommunity.com/id/example/"},
    )

    assert response.status_code == 200
    item = response.json()["recommendations"][0]
    assert item["header_image_url"]
    assert item["steam_store_url"].endswith(f"/app/{item['steam_app_id']}")
    assert item["factor_breakdown"]["personal_fit"]["weight"] == 45
    assert item["factor_breakdown"]["reviews"]["weight"] == 20
    assert item["factor_breakdown"]["activity"]["weight"] == 15
    assert item["factor_breakdown"]["momentum"]["weight"] == 20
    assert item["explanation"]


def test_player_rejects_invalid_profile_and_does_not_echo_key(client):
    response = client.post(
        "/api/player/analyze",
        json={
            "steam_profile_url": "not-a-steam-profile",
            "steam_web_api_key": "visitor-secret",
        },
    )

    assert response.status_code == 422
    assert "visitor-secret" not in response.text


@pytest.mark.parametrize("mode", ["balanced", "discoverability", "audience_potential"])
def test_streamer_simulator_returns_explainable_mode_scores(client, mode):
    response = client.post("/api/streamer/simulate", json={"mode": mode})

    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    item = recommendations[0]
    assert response.json()["simulator"] is True
    assert item["opportunity_score"] >= 0
    assert set(item["breakdown"]) >= {
        "viewer_demand",
        "creator_competition",
        "viewer_channel_ratio",
        "steam_momentum",
        "category_growth",
    }
    fallback_item = next(item for item in recommendations if item["steam_app_id"] == 10)
    assert fallback_item["breakdown"]["steam_momentum"] == 51.1


def test_developer_response_separates_evidence_from_generated_idea(client, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    opportunities = client.get("/api/developer/opportunities")
    assert opportunities.status_code == 200
    opportunity = next(item for item in opportunities.json()["opportunities"] if item["steam_app_id"] == 10)
    assert opportunity["evidence"]
    assert set(opportunity["signals"]) >= {
        "genre_demand",
        "opportunity_gap",
        "review_sentiment",
    }
    assert opportunity["signals"]["review_sentiment"] == 92.0

    concept = client.post("/api/developer/concept", json={"direction": "co-op action"})
    assert concept.status_code == 200
    body = concept.json()
    assert body["data_evidence"]
    assert body["ai_generated_idea"]["title"]
    assert body["ai_generated_idea"]["risks"]


def test_developer_opportunities_uses_a_fixed_number_of_sql_queries(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    observed_at = datetime(2026, 8, 8, tzinfo=timezone.utc)
    with Session(engine) as session:
        for app_id in range(1, 106):
            session.add(
                GameModel(
                    steam_app_id=app_id,
                    name=f"Game {app_id:03d}",
                    peak_ccu=100 + app_id,
                    review_score=0.75,
                )
            )
            session.add(GameTagModel(steam_app_id=app_id, value="Action"))
            session.add(GameGenreModel(steam_app_id=app_id, value="Action"))
            session.add(
                SteamSnapshotModel(
                    steam_app_id=app_id,
                    metric="current_players",
                    value_numeric=100 + app_id,
                    source_name="fixture",
                    source_mode="cached",
                    observed_at=observed_at,
                    confidence="medium",
                )
            )
            session.add(
                StreamingSnapshotModel(
                    steam_app_id=app_id,
                    metric="average_viewers_30d",
                    value_numeric=200 + app_id,
                    source_name="fixture",
                    source_mode="cached",
                    observed_at=observed_at,
                    confidence="medium",
                )
            )
            session.add(
                TrendScoreModel(
                    steam_app_id=app_id,
                    audience="developer",
                    score=50.0,
                    components={} if app_id == 1 else {"genre_demand": 0.5, "opportunity_gap": 0.5},
                    observed_at=observed_at,
                    confidence="medium",
                )
            )
        session.commit()

    statements = []

    def count_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith(("SELECT", "WITH")):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", count_statement)
    monkeypatch.setattr(fusion, "load_trend_artifact", lambda: {})

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/developer/opportunities")
    finally:
        app.dependency_overrides.clear()
        event.remove(engine, "before_cursor_execute", count_statement)
        engine.dispose()

    assert response.status_code == 200
    opportunities = response.json()["opportunities"]
    assert len(opportunities) == 100
    null_signal_item = next(item for item in opportunities if item["steam_app_id"] == 1)
    assert null_signal_item["signals"]["genre_demand"] is None
    assert null_signal_item["signals"]["opportunity_gap"] is None
    assert len(statements) <= 8


def test_fusion_vertical_slice_reaches_health_player_streamer_developer_and_game_detail(client, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    assert client.get("/api/health").json() == {"status": "ok"}

    player_response = client.post(
        "/api/player/analyze",
        json={"steam_profile_url": "https://steamcommunity.com/id/example/"},
    )
    assert player_response.status_code == 200
    recommendation = player_response.json()["recommendations"][0]

    game_response = client.get(f"/api/games/{recommendation['steam_app_id']}")
    assert game_response.status_code == 200
    assert game_response.json()["steam_store_url"].endswith(f"/app/{recommendation['steam_app_id']}")

    for mode in ("balanced", "discoverability", "audience_potential"):
        assert client.post("/api/streamer/simulate", json={"mode": mode}).status_code == 200

    opportunities = client.get("/api/developer/opportunities")
    assert opportunities.status_code == 200
    concept = client.post("/api/developer/concept", json={"direction": "co-op action"})
    assert concept.status_code == 200
    assert concept.json()["data_evidence"]

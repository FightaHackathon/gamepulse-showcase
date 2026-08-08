from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from gamepulse.db.models import Base, GameGenreModel, GameModel, GameTagModel, SteamSnapshotModel, StreamingSnapshotModel, TrendScoreModel
from gamepulse.providers.steam import PlayerLibrary, parse_steam_profile
from gamepulse.web_api.app import app
from gamepulse.web_api.dependencies import get_db_session
from gamepulse.web_api.routes.player import get_player_session
from gamepulse.web_api.routes import player


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
    item = response.json()["recommendations"][0]
    assert response.json()["simulator"] is True
    assert item["opportunity_score"] >= 0
    assert set(item["breakdown"]) >= {
        "viewer_demand",
        "creator_competition",
        "viewer_channel_ratio",
        "steam_momentum",
        "category_growth",
    }


def test_developer_response_separates_evidence_from_generated_idea(client, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    opportunities = client.get("/api/developer/opportunities")
    assert opportunities.status_code == 200
    assert opportunities.json()["opportunities"][0]["evidence"]

    concept = client.post("/api/developer/concept", json={"direction": "co-op action"})
    assert concept.status_code == 200
    body = concept.json()
    assert body["data_evidence"]
    assert body["ai_generated_idea"]["title"]
    assert body["ai_generated_idea"]["risks"]

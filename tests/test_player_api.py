from dataclasses import dataclass

from fastapi.testclient import TestClient

from gamepulse.providers.steam import PlayerLibrary
from gamepulse.services.player_recommendations import PlayerRecommendationResult, PlayerScoreBreakdown
from gamepulse.web_api.app import app
from gamepulse.web_api.routes import player


@dataclass
class FakeSteamProvider:
    api_key: str | None

    def resolve_profile(self, profile_url: str) -> str:
        assert profile_url == "https://steamcommunity.com/id/example/"
        return "76561198000000000"

    def get_library(self, steam_id: str) -> PlayerLibrary:
        assert steam_id == "76561198000000000"
        return PlayerLibrary(
            steam_id=steam_id,
            games=({"appid": 10, "name": "Owned Game", "playtime_forever": 1200},),
            source_name="Steam Web API" if self.api_key else "Public Steam games page",
            complete=bool(self.api_key),
        )


class FakeRecommendationService:
    def recommend(self, library, limit_owned=10, limit_discovery=10):
        owned = PlayerRecommendationResult(
            app_id=10,
            name="Owned Game",
            score=88,
            breakdown=PlayerScoreBreakdown(0.95, 0.90, 0.70, 0.60),
            reasons=("strong match for your most-played tags and genres",),
            owned=True,
            header_image_url="https://example.test/10.jpg",
            review_score=0.9,
            current_players=1200,
            trend_change=0.2,
        )
        discovery = PlayerRecommendationResult(
            app_id=20,
            name="Discovery Game",
            score=84,
            breakdown=PlayerScoreBreakdown(0.90, 0.88, None, None),
            reasons=("strong Steam review quality",),
            owned=False,
            header_image_url="https://example.test/20.jpg",
            review_score=0.88,
        )
        return [owned], [discovery]


def test_player_analyze_returns_profile_and_two_result_groups(monkeypatch):
    monkeypatch.setattr(player, "SteamProvider", FakeSteamProvider)
    monkeypatch.setattr(player, "player_service", lambda: FakeRecommendationService())

    response = TestClient(app).post(
        "/api/player/analyze",
        json={"profile_url": "https://steamcommunity.com/id/example/"},
        headers={"X-GamePulse-Steam-Key": "runtime-only-key"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["steam_id"] == "76561198000000000"
    assert body["library_complete"] is True
    assert body["source_name"] == "Steam Web API"
    assert [item["app_id"] for item in body["owned_recommendations"]] == [10]
    assert [item["app_id"] for item in body["discovery_recommendations"]] == [20]
    assert body["owned_recommendations"][0]["breakdown"] == {
        "personal_fit": 0.95,
        "review_quality": 0.9,
        "current_activity": 0.7,
        "trend_momentum": 0.6,
    }

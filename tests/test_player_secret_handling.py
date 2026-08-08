from fastapi.testclient import TestClient

from gamepulse.providers.steam import PlayerLibrary
from gamepulse.web_api.app import app
from gamepulse.web_api.routes import player
from gamepulse.web_api.settings import WebSettings


SECRET = "visitor-secret-never-persist"


class SecretAwareSteamProvider:
    seen_key = None

    def __init__(self, api_key):
        type(self).seen_key = api_key

    def resolve_profile(self, profile_url):
        return "76561198000000000"

    def get_library(self, steam_id):
        return PlayerLibrary(
            steam_id=steam_id,
            games=(),
            source_name="Steam Web API",
            complete=True,
        )


class EmptyRecommendationService:
    def recommend(self, library, limit_owned=10, limit_discovery=10):
        return [], []


def test_runtime_steam_key_is_request_scoped_and_never_echoed(monkeypatch, caplog):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(player, "SteamProvider", SecretAwareSteamProvider)
    monkeypatch.setattr(player, "player_service", lambda: EmptyRecommendationService())

    response = TestClient(app).post(
        "/api/player/analyze",
        json={"profile_url": "76561198000000000"},
        headers={"X-GamePulse-Steam-Key": SECRET},
    )

    assert response.status_code == 200
    assert SecretAwareSteamProvider.seen_key == SECRET
    assert SECRET not in response.text
    assert SECRET not in caplog.text
    assert not hasattr(WebSettings(database_url="sqlite+pysqlite:///:memory:"), "steam_web_api_key")

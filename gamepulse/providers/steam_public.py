from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import urllib.parse

import httpx

from .contracts import GameIdentity, ProviderError, ProviderMetric


JsonFetcher = Callable[[str, float], object]
STEAM_CURRENT_PLAYERS_URL = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"


def _default_fetch_json(url: str, timeout: float) -> object:
    response = httpx.get(url, timeout=timeout, headers={"Accept": "application/json", "User-Agent": "GamePulse/1.0"})
    response.raise_for_status()
    return response.json()


class SteamCurrentPlayersProvider:
    provider_name = "Steam Web API"
    signal_type = "steam"

    def __init__(
        self,
        *,
        fetch_json: JsonFetcher | None = None,
        timeout_seconds: float = 15.0,
        clock: Callable[[], datetime] | None = None,
    ):
        self.fetch_json = fetch_json or _default_fetch_json
        self.timeout_seconds = timeout_seconds
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def fetch(self, game: GameIdentity) -> list[ProviderMetric]:
        query = urllib.parse.urlencode({"appid": int(game.steam_app_id)})
        url = f"{STEAM_CURRENT_PLAYERS_URL}?{query}"
        try:
            payload = self.fetch_json(url, self.timeout_seconds)
            response = payload.get("response", {}) if isinstance(payload, dict) else {}
            count = response.get("player_count")
            result = response.get("result", 1)
            if result != 1 or count is None:
                raise ValueError("player_count was not present")
            value = max(0, int(count))
        except Exception as exc:
            raise ProviderError(f"Steam current-player request failed: {exc}") from exc
        return [
            ProviderMetric(
                metric="current_players",
                value=value,
                observed_at=self.clock(),
                source_name=self.provider_name,
                source_mode="public_api",
                confidence="high",
                source_url=url,
            )
        ]

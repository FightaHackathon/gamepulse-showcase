from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import urllib.parse

import httpx

from .contracts import GameIdentity, ProviderError, ProviderMetric, ReviewExcerpt


JsonFetcher = Callable[[str, float], object]
STEAM_CURRENT_PLAYERS_URL = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
STEAM_REVIEWS_URL = "https://store.steampowered.com/appreviews/{}"


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

    def fetch_reviews(self, game: GameIdentity) -> list[ReviewExcerpt]:
        """Fetch a small, public Steam review sample for the selected game."""
        excerpts: list[ReviewExcerpt] = []
        for recommendation, review_type in ((True, "positive"), (False, "negative")):
            query = urllib.parse.urlencode(
                {
                    "json": "1",
                    "language": "english",
                    "purchase_type": "all",
                    "filter": "helpful",
                    "review_type": review_type,
                    "num_per_page": "3",
                }
            )
            url = f"{STEAM_REVIEWS_URL.format(int(game.steam_app_id))}?{query}"
            try:
                payload = self.fetch_json(url, self.timeout_seconds)
                if not isinstance(payload, dict) or payload.get("success") != 1:
                    raise ValueError("response did not contain a successful review result")
                reviews = payload.get("reviews")
                if not isinstance(reviews, list):
                    raise ValueError("response did not contain review rows")
                for item in reviews[:3]:
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("review") or "").strip()
                    recommendation_id = str(item.get("recommendationid") or "").strip()
                    if not text or not recommendation_id:
                        continue
                    excerpts.append(
                        ReviewExcerpt(
                            review_id=f"steam-public:{game.steam_app_id}:{recommendation_id}",
                            text=text,
                            recommended=recommendation,
                            helpful_votes=_optional_int(item.get("votes_up")),
                            funny_votes=_optional_int(item.get("votes_funny")),
                            created_at_unix=_optional_int(item.get("timestamp_created")),
                            source_name="Steam Store reviews",
                            source_mode="public_store_api",
                            source_url=url,
                        )
                    )
            except Exception as exc:
                raise ProviderError(f"Steam public review request ({review_type}) failed: {exc}") from exc
        return excerpts


def _optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

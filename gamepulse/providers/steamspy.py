from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import re
import urllib.parse

import httpx

from .contracts import GameIdentity, ProviderError, ProviderMetric


JsonFetcher = Callable[[str, float], object]
STEAMSPY_URL = "https://steamspy.com/api.php"


def _default_fetch_json(url: str, timeout: float) -> object:
    response = httpx.get(url, timeout=timeout, headers={"Accept": "application/json", "User-Agent": "GamePulse/1.0"})
    response.raise_for_status()
    return response.json()


def parse_owners_range(value: object) -> tuple[int | None, int | None]:
    if isinstance(value, bool) or value is None:
        return None, None
    if isinstance(value, int):
        number = max(0, value)
        return number, number
    if isinstance(value, float) and value.is_integer():
        number = max(0, int(value))
        return number, number
    values = []
    for match in re.findall(r"\d[\d,]*", str(value)):
        try:
            values.append(max(0, int(match.replace(",", ""))))
        except ValueError:
            continue
    return (min(values), max(values)) if values else (None, None)


class SteamSpyProvider:
    provider_name = "SteamSpy"

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
        query = urllib.parse.urlencode({"request": "appdetails", "appid": int(game.steam_app_id)})
        url = f"{STEAMSPY_URL}?{query}"
        try:
            payload = self.fetch_json(url, self.timeout_seconds)
            if not isinstance(payload, dict):
                raise ValueError("response was not an object")
            data = payload.get(str(game.steam_app_id), payload)
            if not isinstance(data, dict):
                raise ValueError("response did not contain app details")
            low, high = parse_owners_range(data.get("owners"))
            if low is None or high is None:
                raise ValueError("owners estimate was unavailable")
        except Exception as exc:
            raise ProviderError(f"SteamSpy estimate request failed: {exc}") from exc
        observed = self.clock()
        common = {
            "observed_at": observed,
            "source_name": self.provider_name,
            "source_mode": "public_estimate",
            "confidence": "low",
            "source_url": url,
        }
        return [
            ProviderMetric(metric="owners_low_estimate", value=low, **common),
            ProviderMetric(metric="owners_high_estimate", value=high, **common),
        ]

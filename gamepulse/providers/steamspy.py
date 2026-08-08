"""Bounded SteamSpy app-detail provider for explicitly labelled ownership estimates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Callable

from gamepulse.providers._cache import JsonResponseCache


JsonFetcher = Callable[[str], object]
STEAMSPY_SOURCE = "SteamSpy appdetails API"
STEAMSPY_URL = "https://steamspy.com/api.php?{}"


def _utc_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_fetch_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "GamePulse/1.0"})
    # Avoid inheriting a stale machine-wide proxy; cache/error handling in the
    # provider remains the fallback if direct access is unavailable.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_owners_range(value: object) -> tuple[int | None, int | None]:
    """Parse SteamSpy's human-readable owner interval into bounded integers."""

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
    if not values:
        return None, None
    return min(values), max(values)


@dataclass(frozen=True)
class SteamSpyEstimate:
    steam_app_id: int
    owners_low: int | None
    owners_high: int | None
    source_name: str
    observed_at: str
    confidence: str
    caveat: str
    error: str | None = None


class SteamSpyProvider:
    """Fetch one SteamSpy app detail at a time; never requests a bulk catalogue."""

    def __init__(
        self,
        *,
        fetch_json: JsonFetcher | None = None,
        cache_path: Path | str | None = None,
        cache_ttl_seconds: float = 24 * 60 * 60,
        clock: Callable[[], float] = time.time,
    ):
        self.fetch_json = fetch_json or _default_fetch_json
        self.clock = clock
        self.cache = JsonResponseCache(cache_path, ttl_seconds=cache_ttl_seconds, clock=clock)

    def get_app_estimate(self, app_id: int | str) -> SteamSpyEstimate:
        try:
            normalized_app_id = int(str(app_id).strip())
        except (TypeError, ValueError):
            return self._unavailable(0, "a numeric Steam app ID is required")
        if normalized_app_id <= 0:
            return self._unavailable(normalized_app_id, "Steam app ID must be positive")

        key = f"app:{normalized_app_id}"
        cache_hit = self.cache.get(key)
        if cache_hit is not None and cache_hit.fresh:
            cached = self._normalize(
                normalized_app_id,
                cache_hit.payload,
                observed_at=_utc_timestamp(cache_hit.stored_at),
                source_name=f"{STEAMSPY_SOURCE} (local cache)",
                confidence="cached",
            )
            if cached.error is None:
                return cached

        query = urllib.parse.urlencode({"request": "appdetails", "appid": normalized_app_id})
        try:
            payload = self.fetch_json(STEAMSPY_URL.format(query))
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            if cache_hit is not None:
                fallback = self._normalize(
                    normalized_app_id,
                    cache_hit.payload,
                    observed_at=_utc_timestamp(cache_hit.stored_at),
                    source_name=f"{STEAMSPY_SOURCE} (stale local cache)",
                    confidence="stale-fallback",
                )
                if fallback.error is None:
                    return SteamSpyEstimate(
                        **{**fallback.__dict__, "caveat": f"{fallback.caveat} Network request failed; stale cache used as fallback."}
                    )
            return self._unavailable(normalized_app_id, f"request failed: {exc}")

        result = self._normalize(
            normalized_app_id,
            payload,
            observed_at=_utc_timestamp(self.clock()),
            source_name=STEAMSPY_SOURCE,
            confidence="estimate",
        )
        if result.error is None:
            self.cache.put(key, payload)
        return result

    def get_app_details(self, app_id: int | str) -> SteamSpyEstimate:
        return self.get_app_estimate(app_id)

    def _normalize(
        self,
        app_id: int,
        payload: object,
        *,
        observed_at: str,
        source_name: str,
        confidence: str,
    ) -> SteamSpyEstimate:
        if not isinstance(payload, dict):
            return self._unavailable(app_id, "response was not a JSON object", observed_at=observed_at)
        data = payload
        if isinstance(payload.get(str(app_id)), dict):
            data = payload[str(app_id)]
        elif isinstance(payload.get("data"), dict):
            data = payload["data"]
        owners_low, owners_high = parse_owners_range(data.get("owners"))
        if owners_low is None or owners_high is None:
            return self._unavailable(app_id, "response did not contain a parseable owners estimate", observed_at=observed_at)
        return SteamSpyEstimate(
            steam_app_id=app_id,
            owners_low=owners_low,
            owners_high=owners_high,
            source_name=source_name,
            observed_at=observed_at,
            confidence=confidence,
            caveat="SteamSpy owners are non-authoritative estimates, not verified sales, units sold, downloads, or revenue.",
        )

    def _unavailable(self, app_id: int, error: str, *, observed_at: str | None = None) -> SteamSpyEstimate:
        return SteamSpyEstimate(
            steam_app_id=app_id,
            owners_low=None,
            owners_high=None,
            source_name=STEAMSPY_SOURCE,
            observed_at=observed_at or _utc_timestamp(self.clock()),
            confidence="unavailable",
            caveat=f"SteamSpy estimate unavailable: {error}",
            error=error,
        )

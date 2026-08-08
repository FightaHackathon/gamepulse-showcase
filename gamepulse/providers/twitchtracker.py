"""Bounded TwitchTracker game-summary provider using its documented JSON API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request
from collections.abc import Callable

from gamepulse.providers._cache import JsonResponseCache


JsonFetcher = Callable[[str], object]
TWITCHTRACKER_SOURCE = "TwitchTracker API"
TWITCHTRACKER_URL = "https://twitchtracker.com/api/games/summary/{}"


def _utc_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_fetch_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "GamePulse/1.0"})
    # Public sources should not inherit a stale machine-wide proxy setting.
    # The desktop client makes bounded, direct requests and still reports a
    # recoverable unavailable result when direct network access is blocked.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        number = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, number)


def _first_integer(payload: dict, *fields: str) -> int | None:
    for field in fields:
        value = _integer(payload.get(field))
        if value is not None:
            return value
    return None


def _payload_observed_at(payload: dict, fallback: str) -> str:
    for field in ("observed_at", "updated_at", "timestamp", "date"):
        value = payload.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return _utc_timestamp(float(value))
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


@dataclass(frozen=True)
class TwitchTrackerSummary:
    requested_game: str
    game_id: str | None
    game_name: str | None
    viewer_count: int | None
    channel_count: int | None
    average_viewers: int | None
    peak_viewers: int | None
    hours_watched: float | None
    source_name: str
    observed_at: str
    confidence: str
    caveat: str
    error: str | None = None

    @property
    def audience_value(self) -> int | None:
        """Compatibility name for callers that use source-neutral audience fields."""

        return self.viewer_count

    @property
    def live_channels(self) -> int | None:
        return self.channel_count


class TwitchTrackerProvider:
    """Fetch one TwitchTracker category summary at a time."""

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

    def get_game_summary(self, category: str | int) -> TwitchTrackerSummary:
        requested_game = str(category).strip()
        if not requested_game:
            return self._unavailable("a Twitch category ID or name is required")

        cache_hit = self.cache.get(f"game:{requested_game.casefold()}")
        if cache_hit is not None and cache_hit.fresh:
            cached = self._normalize(
                requested_game,
                cache_hit.payload,
                observed_at=_utc_timestamp(cache_hit.stored_at),
                source_name=f"{TWITCHTRACKER_SOURCE} (local cache)",
                confidence="cached",
            )
            if cached.error is None:
                return cached

        url = TWITCHTRACKER_URL.format(urllib.parse.quote(requested_game, safe=""))
        try:
            payload = self.fetch_json(url)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            if cache_hit is not None:
                fallback = self._normalize(
                    requested_game,
                    cache_hit.payload,
                    observed_at=_utc_timestamp(cache_hit.stored_at),
                    source_name=f"{TWITCHTRACKER_SOURCE} (stale local cache)",
                    confidence="stale-fallback",
                )
                if fallback.error is None:
                    return TwitchTrackerSummary(
                        **{**fallback.__dict__, "caveat": f"{fallback.caveat} Network request failed; stale cache used as fallback."}
                    )
            return self._unavailable(f"request failed: {exc}")

        result = self._normalize(
            requested_game,
            payload,
            observed_at=_utc_timestamp(self.clock()),
            source_name=TWITCHTRACKER_SOURCE,
            confidence="live",
        )
        if result.error is None:
            self.cache.put(f"game:{requested_game.casefold()}", payload)
        return result

    def get_summary(self, category: str | int) -> TwitchTrackerSummary:
        return self.get_game_summary(category)

    def _normalize(
        self,
        requested_game: str,
        payload: object,
        *,
        observed_at: str,
        source_name: str,
        confidence: str,
    ) -> TwitchTrackerSummary:
        if not isinstance(payload, dict):
            return self._unavailable("response was not a JSON object", requested_game=requested_game, observed_at=observed_at)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        observed_at = _payload_observed_at(data, observed_at)
        game = data.get("game") if isinstance(data.get("game"), dict) else {}
        game_id = str(game.get("id") or data.get("game_id") or (requested_game if requested_game.isdigit() else "")) or None
        game_name = str(game.get("name") or data.get("game_name") or (requested_game if not requested_game.isdigit() else "")) or None
        viewer_count = _first_integer(data, "viewers", "viewer_count", "current_viewers")
        channel_count = _first_integer(data, "channels", "live_channels", "channel_count", "streams", "stream_count")
        average_viewers = _first_integer(data, "average_viewers", "avg_viewers")
        peak_viewers = _first_integer(data, "peak_viewers")
        hours_watched = None
        try:
            if data.get("hours_watched") is not None:
                hours_watched = max(0.0, float(data["hours_watched"]))
        except (TypeError, ValueError):
            hours_watched = None
        if viewer_count is None and channel_count is None and average_viewers is None and peak_viewers is None and hours_watched is None:
            return self._unavailable(
                "response contained no usable audience or channel metrics",
                requested_game=requested_game,
                observed_at=observed_at,
            )
        return TwitchTrackerSummary(
            requested_game=requested_game,
            game_id=game_id,
            game_name=game_name,
            viewer_count=viewer_count,
            channel_count=channel_count,
            average_viewers=average_viewers,
            peak_viewers=peak_viewers,
            hours_watched=hours_watched,
            source_name=source_name,
            observed_at=observed_at,
            confidence=confidence,
            caveat=(
                "TwitchTracker public summary metrics are observed category estimates, not verified sales or revenue."
                + (" Data was reused from the local cache." if confidence == "cached" else "")
            ),
        )

    def _unavailable(
        self,
        error: str,
        *,
        requested_game: str = "",
        observed_at: str | None = None,
    ) -> TwitchTrackerSummary:
        return TwitchTrackerSummary(
            requested_game=requested_game,
            game_id=None,
            game_name=None,
            viewer_count=None,
            channel_count=None,
            average_viewers=None,
            peak_viewers=None,
            hours_watched=None,
            source_name=TWITCHTRACKER_SOURCE,
            observed_at=observed_at or _utc_timestamp(self.clock()),
            confidence="unavailable",
            caveat=f"TwitchTracker summary unavailable: {error}",
            error=error,
        )

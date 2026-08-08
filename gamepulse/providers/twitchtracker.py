from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import urllib.parse

import httpx

from .contracts import GameIdentity, ProviderError, ProviderMetric


JsonFetcher = Callable[[str, float], object]
TWITCHTRACKER_SUMMARY_URL = "https://twitchtracker.com/api/games/summary/{}"


def _default_fetch_json(url: str, timeout: float) -> object:
    response = httpx.get(url, timeout=timeout, headers={"Accept": "application/json", "User-Agent": "GamePulse/1.0"})
    response.raise_for_status()
    return response.json()


def _first(data: dict, *keys: str):
    for key in keys:
        if data.get(key) is not None:
            return data[key]
    return None


class TwitchTrackerProvider:
    provider_name = "TwitchTracker"

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
        lookup = urllib.parse.quote(str(game.twitch_lookup), safe="")
        url = TWITCHTRACKER_SUMMARY_URL.format(lookup)
        try:
            payload = self.fetch_json(url, self.timeout_seconds)
            if not isinstance(payload, dict):
                raise ValueError("response was not an object")
            data = payload.get("data", payload)
            if not isinstance(data, dict):
                raise ValueError("response did not contain summary data")
            rank = _first(data, "rank", "game_rank")
            hours = _first(data, "hours_watched", "watched_hours")
            if hours is None:
                minutes = _first(data, "minutes_watched", "watched_minutes")
                hours = float(minutes) / 60.0 if minutes is not None else None
            viewers = _first(data, "avg_viewers", "average_viewers")
            channels = _first(data, "avg_channels", "average_channels")
        except Exception as exc:
            raise ProviderError(f"TwitchTracker summary request failed: {exc}") from exc

        observed = self.clock()
        common = {
            "observed_at": observed,
            "source_name": self.provider_name,
            "source_mode": "public_30d_summary",
            "confidence": "medium",
            "source_url": url,
        }
        metrics: list[ProviderMetric] = []
        for metric, value in (
            ("twitch_rank_30d", rank),
            ("hours_watched_30d", hours),
            ("average_viewers_30d", viewers),
            ("average_channels_30d", channels),
        ):
            if value is not None:
                metrics.append(
                    ProviderMetric(
                        metric=metric,
                        value=float(value) if metric == "hours_watched_30d" else value,
                        **common,
                    )
                )
        if viewers is not None and channels is not None and float(channels) > 0:
            metrics.append(
                ProviderMetric(
                    metric="viewer_channel_ratio_30d",
                    value=float(viewers) / float(channels),
                    **common,
                )
            )
        if not metrics:
            raise ProviderError("TwitchTracker summary did not contain recognized game metrics")
        return metrics

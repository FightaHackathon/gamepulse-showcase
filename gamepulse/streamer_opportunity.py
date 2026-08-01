"""Explainable opportunity ranking for Streamer Mode."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Literal

from gamepulse.providers.twitch import GameTrend, Snapshot


@dataclass(frozen=True)
class StreamerProfile:
    preferred_tags: tuple[str, ...] = ()
    channel_size_tier: str = "emerging"
    strategy: str = "balanced"


@dataclass(frozen=True)
class OpportunityComponents:
    demand: float
    reach: float
    growth: float
    competition: float
    preference_fit: float = 0.0


@dataclass(frozen=True)
class GameOpportunity:
    game_id: str
    name: str
    score: float
    reasons: tuple[str, ...]
    viewer_count: int
    channel_count: int
    score_band: str = "Competitive opportunity"
    components: OpportunityComponents = OpportunityComponents(0.0, 0.0, 0.0, 0.0)
    viewer_to_channel: float = 0.0


SnapshotStatus = Literal["live", "fresh_snapshot", "stale_snapshot"]


@dataclass(frozen=True)
class SnapshotFreshness:
    status: SnapshotStatus
    label: str
    age_hours: float | None
    message: str


def score_band(score: float) -> str:
    """Return a human-readable band for a normalized 0..1 score."""
    if score >= 0.75:
        return "Strong opportunity"
    if score >= 0.55:
        return "Promising opportunity"
    return "Competitive opportunity"


def _normalized_game_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def find_matching_opportunity(opportunities, game_name: str):
    """Match a Steam-selected game to a Twitch category by normalized name."""
    target = _normalized_game_name(game_name)
    return next((item for item in opportunities if _normalized_game_name(item.name) == target), None)


def _parse_observed_at(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def evaluate_snapshot_freshness(snapshot: Snapshot, now: datetime | None = None, freshness_hours: int = 48) -> SnapshotFreshness:
    """Classify live and cached Twitch data so the UI can show provenance clearly."""
    if snapshot.mode.casefold() == "live":
        return SnapshotFreshness("live", "Live", None, "Live Twitch observations are available.")
    try:
        observed = _parse_observed_at(snapshot.observed_at)
    except (TypeError, ValueError):
        return SnapshotFreshness("stale_snapshot", "Snapshot date unavailable", None, "The cached Twitch snapshot date could not be verified.")
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (reference - observed).total_seconds() / 3600)
    if age_hours <= max(1, int(freshness_hours)):
        return SnapshotFreshness("fresh_snapshot", "Cached snapshot", age_hours, f"Cached Twitch observations from {snapshot.observed_at}.")
    return SnapshotFreshness("stale_snapshot", "Stale snapshot", age_hours, f"Cached Twitch observations are {age_hours:.0f} hours old; treat this as directional.")


def score_game_opportunities(trends: list[GameTrend], profile: StreamerProfile) -> list[GameOpportunity]:
    if not trends:
        return []
    max_viewers = max(max(0, item.viewer_count) for item in trends) or 1
    max_ratio = max((max(0, item.viewer_count) / max(item.channel_count, 1) for item in trends), default=1) or 1
    max_channels = max(max(0, item.channel_count) for item in trends) or 1
    results = []
    for trend in trends:
        viewers = max(0, trend.viewer_count)
        channels = max(0, trend.channel_count)
        viewer_to_channel = viewers / max(channels, 1)
        demand = viewers / max_viewers
        reach = viewer_to_channel / max_ratio
        growth = max(0.0, min(1.0, trend.growth_score))
        competition = 1.0 - min(1.0, channels / max_channels)
        tier_weights = {
            "emerging": (0.2, 0.35, 0.15, 0.25),
            "mid-size": (0.3, 0.3, 0.2, 0.15),
            "large": (0.4, 0.2, 0.2, 0.15),
        }
        weights = tier_weights.get(profile.channel_size_tier.casefold(), tier_weights["mid-size"])
        strategy = profile.strategy.casefold()
        if strategy == "reach":
            weights = (weights[0] - 0.1, weights[1] + 0.1, weights[2], weights[3])
        elif strategy == "growth":
            weights = (weights[0] - 0.1, weights[1], weights[2] + 0.1, weights[3])
        base_score = demand * weights[0] + reach * weights[1] + growth * weights[2] + competition * weights[3] + 0.05
        preferred = {value.casefold() for value in profile.preferred_tags}
        trend_tags = {str(value).casefold() for value in getattr(trend, "tags", ())}
        preference_fit = len(preferred & trend_tags) / len(preferred) if preferred and trend_tags else 0.0
        score = min(1.0, base_score + preference_fit * 0.05)
        reasons = [f"{viewers:,} observed viewers across {channels:,} channels", f"viewer-to-channel opportunity {viewer_to_channel:.1f}"]
        if growth > 0.25:
            reasons.append("recent growth signal is positive")
        if channels and viewer_to_channel >= 50:
            reasons.append("demand is not evenly spread across too many channels")
        if competition >= 0.6:
            reasons.append("competition is relatively reachable")
        if preference_fit:
            reasons.append("matches your preferred category tags")
        components = OpportunityComponents(round(demand, 4), round(reach, 4), round(growth, 4), round(competition, 4), round(preference_fit, 4))
        results.append(GameOpportunity(trend.game_id, trend.name, round(score, 4), tuple(reasons), viewers, channels, score_band(score), components, round(viewer_to_channel, 1)))
    results.sort(key=lambda item: (-item.score, item.name.casefold(), item.game_id))
    return results

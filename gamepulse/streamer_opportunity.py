"""Explainable, source-neutral opportunity ranking for Streamer Mode."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import Literal, Mapping

from gamepulse.providers.contracts import GameSignal, SignalSnapshot
from gamepulse.providers.twitch import GameTrend


@dataclass(frozen=True)
class StreamerProfile:
    preferred_tags: tuple[str, ...] = ()
    channel_size_tier: str = "emerging"
    strategy: str = "balanced"
    preferred_genres: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpportunityComponents:
    audience: float | None = None
    growth: float | None = None
    competition: float | None = None
    preference_fit: float | None = None
    sentiment: float | None = None
    promotion: float | None = None
    freshness: float | None = None

    @property
    def demand(self) -> float:
        """Compatibility alias for older UI/tests."""

        return float(self.audience or 0.0)

    @property
    def reach(self) -> float:
        """Compatibility alias; reachability is represented by competition."""

        return float(self.competition or 0.0)


@dataclass(frozen=True)
class GameOpportunity:
    game_id: str
    name: str
    score: float
    reasons: tuple[str, ...]
    audience_value: float | None
    audience_metric: str | None
    competition_value: float | None
    competition_metric: str | None
    score_band: str = "Competitive opportunity"
    components: OpportunityComponents = OpportunityComponents()
    platform: str = "Unknown"
    source_name: str = ""
    source_mode: str = "Unknown"
    observed_at: str = ""
    confidence: str = "unknown"
    unavailable_components: tuple[str, ...] = ()

    @property
    def viewer_count(self) -> int | None:
        if self.audience_metric != "twitch_viewers" or self.audience_value is None:
            return None
        return max(0, int(self.audience_value))

    @property
    def channel_count(self) -> int | None:
        if self.competition_metric != "twitch_live_channels" or self.competition_value is None:
            return None
        return max(0, int(self.competition_value))

    @property
    def viewer_to_channel(self) -> float | None:
        if self.viewer_count is None or self.channel_count in {None, 0}:
            return None
        return self.viewer_count / self.channel_count


SnapshotStatus = Literal[
    "live",
    "fresh_snapshot",
    "stale_snapshot",
    "prepared",
    "manual",
    "creator_submitted",
    "unavailable",
]


@dataclass(frozen=True)
class SnapshotFreshness:
    status: SnapshotStatus
    label: str
    age_hours: float | None
    message: str


BASE_WEIGHTS = {
    "audience": 0.30,
    "growth": 0.20,
    "competition": 0.20,
    "preference_fit": 0.10,
    "sentiment": 0.10,
    "promotion": 0.05,
    "freshness": 0.05,
}

STRATEGY_WEIGHTS = {
    "balanced": BASE_WEIGHTS,
    "reach": {
        "audience": 0.30,
        "growth": 0.15,
        "competition": 0.30,
        "preference_fit": 0.10,
        "sentiment": 0.10,
        "promotion": 0.025,
        "freshness": 0.025,
    },
    "growth": {
        "audience": 0.25,
        "growth": 0.35,
        "competition": 0.15,
        "preference_fit": 0.10,
        "sentiment": 0.10,
        "promotion": 0.025,
        "freshness": 0.025,
    },
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def score_band(score: float) -> str:
    if score >= 0.75:
        return "Strong opportunity"
    if score >= 0.55:
        return "Promising opportunity"
    return "Competitive opportunity"


def _normalized_game_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def find_matching_opportunity(opportunities, game_name: str):
    target = _normalized_game_name(game_name)
    return next((item for item in opportunities if _normalized_game_name(item.name) == target), None)


def _parse_observed_at(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def evaluate_snapshot_freshness(
    snapshot: SignalSnapshot,
    now: datetime | None = None,
    freshness_hours: int = 48,
) -> SnapshotFreshness:
    """Classify provenance without assuming the source is Twitch."""

    mode = str(snapshot.mode or "").strip().casefold()
    if mode == "live":
        return SnapshotFreshness("live", "Live", None, "Live provider observations are available.")
    if mode == "prepared":
        return SnapshotFreshness("prepared", "Prepared dataset", None, "Using prepared GamePulse data with source-specific observation dates.")
    if mode == "manual":
        return SnapshotFreshness("manual", "Manual", None, "Using manually maintained data; it is not a live platform-wide observation.")
    if mode == "creator submitted":
        return SnapshotFreshness("creator_submitted", "Creator submitted", None, "Using creator-submitted data; it is not a live platform-wide observation.")
    if mode == "unavailable":
        return SnapshotFreshness("unavailable", "Unavailable", None, "No eligible signal provider is currently available.")

    try:
        observed = _parse_observed_at(snapshot.observed_at)
    except (TypeError, ValueError):
        return SnapshotFreshness("stale_snapshot", "Snapshot date unavailable", None, "The snapshot observation date could not be verified.")
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (reference - observed).total_seconds() / 3600)
    if age_hours <= max(1, int(freshness_hours)):
        return SnapshotFreshness("fresh_snapshot", "Fresh snapshot", age_hours, f"Snapshot observed {snapshot.observed_at}.")
    return SnapshotFreshness("stale_snapshot", "Stale snapshot", age_hours, f"Snapshot is {age_hours:.0f} hours old; treat it as directional.")


def renormalized_weighted_score(
    components: Mapping[str, float | None],
    weights: Mapping[str, float],
) -> float:
    """Score only available components and renormalize their configured weights."""

    available = {
        name: (_clamp(value), max(0.0, float(weights.get(name, 0.0))))
        for name, value in components.items()
        if value is not None and float(weights.get(name, 0.0)) > 0
    }
    total_weight = sum(weight for _value, weight in available.values())
    if total_weight <= 0:
        return 0.0
    return _clamp(sum(value * weight for value, weight in available.values()) / total_weight)


def _legacy_signal(item: GameTrend) -> GameSignal:
    return item.to_signal(source_name="Legacy Twitch trend", mode="Imported")


def _as_signal(item: object) -> GameSignal:
    if isinstance(item, GameSignal):
        return item
    if isinstance(item, GameTrend):
        return _legacy_signal(item)
    audience = getattr(item, "audience_value", getattr(item, "viewer_count", None))
    competition = getattr(item, "competition_value", getattr(item, "channel_count", None))
    audience_metric = getattr(item, "audience_metric", None)
    competition_metric = getattr(item, "competition_metric", None)
    if audience_metric is None and getattr(item, "viewer_count", None) is not None:
        audience_metric = "twitch_viewers"
    if competition_metric is None and getattr(item, "channel_count", None) is not None:
        competition_metric = "twitch_live_channels"
    return GameSignal(
        game_id=str(getattr(item, "game_id", "")),
        name=str(getattr(item, "name", "")),
        audience_value=None if audience is None else float(audience),
        audience_metric=audience_metric,
        competition_value=None if competition is None else float(competition),
        competition_metric=competition_metric,
        growth_score=getattr(item, "growth_score", None),
        tags=tuple(getattr(item, "tags", ()) or ()),
        genres=tuple(getattr(item, "genres", ()) or ()),
        platform=str(getattr(item, "platform", "Unknown")),
        source_name=str(getattr(item, "source_name", "Legacy signal")),
        observed_at=str(getattr(item, "observed_at", "")),
        confidence=str(getattr(item, "confidence", "unknown")),
        source_mode=str(getattr(item, "source_mode", "Unknown")),
        sentiment_score=getattr(item, "sentiment_score", None),
        promotion_score=getattr(item, "promotion_score", None),
        freshness_score=getattr(item, "freshness_score", None),
    )


def _weights(profile: StreamerProfile) -> dict[str, float]:
    weights = dict(STRATEGY_WEIGHTS.get(profile.strategy.casefold(), BASE_WEIGHTS))
    tier = profile.channel_size_tier.casefold()
    if tier == "emerging":
        shift = min(0.05, weights["audience"])
        weights["audience"] -= shift
        weights["competition"] += shift
    elif tier == "large":
        shift = min(0.05, weights["competition"])
        weights["competition"] -= shift
        weights["audience"] += shift
    return weights


def _metric_group_max(signals: list[GameSignal], field: str, metric_field: str) -> dict[str, float]:
    maxima: dict[str, float] = {}
    for signal in signals:
        metric = getattr(signal, metric_field)
        value = getattr(signal, field)
        if metric and value is not None and float(value) >= 0:
            maxima[str(metric)] = max(maxima.get(str(metric), 0.0), float(value))
    return maxima


def _audience_component(signal: GameSignal, maxima: Mapping[str, float]) -> float | None:
    if signal.audience_value is None or not signal.audience_metric:
        return None
    value = max(0.0, float(signal.audience_value))
    maximum = max(0.0, float(maxima.get(signal.audience_metric, 0.0)))
    if maximum <= 0:
        return 0.0
    return _clamp(math.log1p(value) / math.log1p(maximum))


def _competition_component(signal: GameSignal, maxima: Mapping[str, float]) -> float | None:
    if signal.competition_value is None or not signal.competition_metric:
        return None
    value = max(0.0, float(signal.competition_value))
    maximum = max(0.0, float(maxima.get(signal.competition_metric, 0.0)))
    if maximum <= 0:
        return 1.0 if value == 0 else None
    return _clamp(1.0 - value / maximum)


def _preference_component(signal: GameSignal, profile: StreamerProfile) -> float | None:
    preferred = {str(value).casefold() for value in (*profile.preferred_tags, *profile.preferred_genres) if str(value).strip()}
    if not preferred:
        return None
    signal_values = {str(value).casefold() for value in (*signal.tags, *signal.genres) if str(value).strip()}
    return len(preferred & signal_values) / len(preferred) if signal_values else 0.0


def audience_metric_label(metric: str | None) -> str:
    return {
        "steam_current_players": "current Steam players",
        "steam_peak_ccu": "Steam peak CCU",
        "steam_peak_ccu_prepared": "prepared Steam peak CCU",
        "twitch_viewers": "observed Twitch viewers",
        "imported_audience": "imported audience signal",
    }.get(str(metric or ""), str(metric or "audience signal").replace("_", " "))


def competition_metric_label(metric: str | None) -> str:
    return {
        "twitch_live_channels": "observed live channels",
    }.get(str(metric or ""), str(metric or "competition signal").replace("_", " "))


def score_game_opportunities(
    trends: list[GameSignal] | list[GameTrend] | SignalSnapshot[GameSignal],
    profile: StreamerProfile,
) -> list[GameOpportunity]:
    if isinstance(trends, SignalSnapshot):
        signals = [_as_signal(item) for item in trends.data]
        snapshot_mode = trends.mode
        snapshot_source = trends.source_name
        snapshot_observed_at = trends.observed_at
        snapshot_confidence = trends.confidence
    else:
        signals = [_as_signal(item) for item in trends]
        snapshot_mode = snapshot_source = snapshot_observed_at = ""
        snapshot_confidence = "unknown"
    if not signals:
        return []

    audience_maxima = _metric_group_max(signals, "audience_value", "audience_metric")
    competition_maxima = _metric_group_max(signals, "competition_value", "competition_metric")
    weights = _weights(profile)
    results: list[GameOpportunity] = []
    for signal in signals:
        audience = _audience_component(signal, audience_maxima)
        growth = None if signal.growth_score is None else _clamp(float(signal.growth_score))
        competition = _competition_component(signal, competition_maxima)
        preference_fit = _preference_component(signal, profile)
        sentiment = None if signal.sentiment_score is None else _clamp(float(signal.sentiment_score))
        promotion = None if signal.promotion_score is None else _clamp(float(signal.promotion_score))
        freshness = None if signal.freshness_score is None else _clamp(float(signal.freshness_score))
        values = {
            "audience": audience,
            "growth": growth,
            "competition": competition,
            "preference_fit": preference_fit,
            "sentiment": sentiment,
            "promotion": promotion,
            "freshness": freshness,
        }
        score = round(renormalized_weighted_score(values, weights), 4)
        unavailable = tuple(name for name, value in values.items() if value is None)

        reasons: list[str] = []
        if signal.audience_value is not None:
            reasons.append(f"{signal.audience_value:,.0f} {audience_metric_label(signal.audience_metric)}")
        else:
            reasons.append("Audience activity is unavailable for this source")
        if growth is not None:
            if growth > 0.6:
                reasons.append("Recent activity momentum is strong")
            elif growth > 0.5:
                reasons.append("Recent activity momentum is positive")
            else:
                reasons.append("Recent activity momentum is limited")
        if competition is None:
            reasons.append("Competition signal unavailable and was excluded from scoring")
        elif signal.competition_value is not None:
            reasons.append(f"{signal.competition_value:,.0f} {competition_metric_label(signal.competition_metric)} observed")
        if preference_fit is not None and preference_fit > 0:
            reasons.append("Matches your preferred genre/tag signals")
        if sentiment is not None and sentiment >= 0.75:
            reasons.append("Public review sentiment is strong")

        components = OpportunityComponents(
            audience=round(audience, 4) if audience is not None else None,
            growth=round(growth, 4) if growth is not None else None,
            competition=round(competition, 4) if competition is not None else None,
            preference_fit=round(preference_fit, 4) if preference_fit is not None else None,
            sentiment=round(sentiment, 4) if sentiment is not None else None,
            promotion=round(promotion, 4) if promotion is not None else None,
            freshness=round(freshness, 4) if freshness is not None else None,
        )
        results.append(
            GameOpportunity(
                game_id=signal.game_id,
                name=signal.name,
                score=score,
                reasons=tuple(reasons),
                audience_value=signal.audience_value,
                audience_metric=signal.audience_metric,
                competition_value=signal.competition_value,
                competition_metric=signal.competition_metric,
                score_band=score_band(score),
                components=components,
                platform=signal.platform,
                source_name=signal.source_name or snapshot_source,
                source_mode=signal.source_mode or snapshot_mode,
                observed_at=signal.observed_at or snapshot_observed_at,
                confidence=signal.confidence or snapshot_confidence,
                unavailable_components=unavailable,
            )
        )
    results.sort(key=lambda item: (-item.score, item.name.casefold(), item.game_id))
    return results

"""Explainable opportunity ranking for Streamer Mode."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import Literal, Mapping

from gamepulse.providers.twitch import GameTrend, Snapshot


MIN_VIABLE_VIEWERS = 100
MIN_VIABLE_CHANNELS = 2
REACH_RATIO_CAP = 250.0

DEFAULT_WEIGHTS = {
    "demand": 0.20,
    "reachability": 0.20,
    "momentum": 0.20,
    "competition": 0.15,
    "stability": 0.10,
    "preference_fit": 0.10,
    "tier_suitability": 0.05,
}

STRATEGY_WEIGHTS = {
    "balanced": DEFAULT_WEIGHTS,
    "reach": {
        "demand": 0.15,
        "reachability": 0.30,
        "momentum": 0.15,
        "competition": 0.15,
        "stability": 0.10,
        "preference_fit": 0.10,
        "tier_suitability": 0.05,
    },
    "growth": {
        "demand": 0.15,
        "reachability": 0.15,
        "momentum": 0.30,
        "competition": 0.15,
        "stability": 0.10,
        "preference_fit": 0.10,
        "tier_suitability": 0.05,
    },
    "community": {
        "demand": 0.10,
        "reachability": 0.15,
        "momentum": 0.15,
        "competition": 0.15,
        "stability": 0.20,
        "preference_fit": 0.20,
        "tier_suitability": 0.05,
    },
}

TIER_RANGES = {
    "emerging": ((1_000, 50_000), (5, 500)),
    "mid-size": ((10_000, 150_000), (50, 3_000)),
    "large": ((30_000, 1_000_000), (500, 20_000)),
}


@dataclass(frozen=True)
class StreamerProfile:
    """Streamer inputs used by the category decision score."""

    preferred_tags: tuple[str, ...] = ()
    channel_size_tier: str = "emerging"
    strategy: str = "balanced"
    preferred_genres: tuple[str, ...] = ()
    preferred_steam_tags: tuple[str, ...] = ()
    preferred_twitch_tags: tuple[str, ...] = ()
    preferred_languages: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoricalGameFeatures:
    """Historical evidence used for momentum, stability, and confidence."""

    growth_score: float | None = None
    volatility: float | None = None
    observation_count: int = 0
    observation_consistency: float | None = None
    viewer_history: tuple[int, ...] = ()
    observed_at: str | None = None
    growth: float | None = None


@dataclass(frozen=True)
class OpportunityComponents:
    demand: float
    reach: float
    growth: float
    competition: float
    preference_fit: float = 0.0
    stability: float = 0.0
    tier_suitability: float = 0.0

    @property
    def reachability(self) -> float:
        return self.reach

    @property
    def momentum(self) -> float:
        return self.growth

    @property
    def values(self) -> dict[str, float]:
        return {
            "demand": self.demand,
            "reachability": self.reachability,
            "momentum": self.momentum,
            "competition": self.competition,
            "stability": self.stability,
            "preference_fit": self.preference_fit,
            "tier_suitability": self.tier_suitability,
        }


@dataclass(frozen=True)
class GameOpportunity:
    game_id: str
    name: str
    score: float
    reasons: tuple[str, ...]
    viewer_count: int
    channel_count: int
    score_band: str = "Competitive category"
    components: OpportunityComponents = OpportunityComponents(0.0, 0.0, 0.0, 0.0)
    viewer_to_channel: float = 0.0
    cautions: tuple[str, ...] = ()
    trend_direction: str = "Unavailable"
    confidence_score: float = 0.0
    confidence_band: str = "Very low confidence"
    source_mode: str = "Unknown"
    observed_at: str | None = None
    steam_app_id: int | None = None


SnapshotStatus = Literal["live", "fresh_snapshot", "stale_snapshot"]


@dataclass(frozen=True)
class SnapshotFreshness:
    status: SnapshotStatus
    label: str
    age_hours: float | None
    message: str


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


def score_band(score: float) -> str:
    """Return a stable label for a 0..100 opportunity score."""
    value = _clamp(float(score), 0.0, 100.0)
    if value >= 80:
        return "Excellent opportunity"
    if value >= 65:
        return "Strong opportunity"
    if value >= 50:
        return "Promising opportunity"
    if value >= 30:
        return "Competitive category"
    return "Weak evidence"


def confidence_band(score: float) -> str:
    if score >= 0.80:
        return "High confidence"
    if score >= 0.55:
        return "Moderate confidence"
    if score >= 0.30:
        return "Low confidence"
    return "Very low confidence"


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


_MISSING = object()


def _field(value: object, *names: str, default: object = None) -> object:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if not isinstance(value, Mapping) and hasattr(value, name):
            return getattr(value, name)
    return default


def _as_float(value: object, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _history_for(historical_features: Mapping[str, object] | None, game_id: str) -> object | None:
    if not historical_features:
        return None
    return historical_features.get(game_id)


def _mapping_for(verified_steam_mappings: Mapping[str, object] | None, game_id: str) -> object | None:
    if not verified_steam_mappings:
        return None
    return verified_steam_mappings.get(game_id)


def _is_reliable_mapping(mapping: object | None) -> bool:
    if mapping is None:
        return False
    reliable = _field(mapping, "is_reliable", default=_MISSING)
    if reliable is not _MISSING:
        return bool(reliable)
    verified = _field(mapping, "manual_verified", "manual_verification", "verified", default=_MISSING)
    if verified is not _MISSING:
        return bool(verified)
    method = str(_field(mapping, "match_method", default="")).casefold()
    score = _as_float(_field(mapping, "match_score", default=0.0), 0.0) or 0.0
    return method == "exact" or (method == "fuzzy" and score >= 0.90)


def _steam_app_id(mapping: object | None) -> int | None:
    value = _field(mapping, "steam_app_id", "app_id", default=None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _feature_values(features: object | None, name: str) -> set[str]:
    values = _field(features, name, default=())
    if isinstance(values, str):
        values = (values,)
    try:
        return {str(item).casefold() for item in values if str(item).strip()}
    except TypeError:
        return set()


def _steam_features_for(steam_features: Mapping[object, object] | None, game_id: str, app_id: int | None) -> object | None:
    if not steam_features:
        return None
    if app_id is not None and app_id in steam_features:
        return steam_features[app_id]
    if app_id is not None and str(app_id) in steam_features:
        return steam_features[str(app_id)]
    return steam_features.get(game_id)


def _preference_fit(
    trend: GameTrend,
    profile: StreamerProfile,
    mapping: object | None,
    steam_features: Mapping[object, object] | None,
) -> tuple[float, bool]:
    group_scores: list[float] = []
    twitch_preferences = {str(item).casefold() for item in (*profile.preferred_tags, *profile.preferred_twitch_tags)}
    twitch_tags = {str(item).casefold() for item in getattr(trend, "tags", ())}
    if twitch_preferences:
        group_scores.append(len(twitch_preferences & twitch_tags) / len(twitch_preferences))

    language_preferences = {str(item).casefold() for item in profile.preferred_languages}
    language_values = {str(item[0]).casefold() for item in getattr(trend, "language_distribution", ()) if isinstance(item, (tuple, list)) and len(item) == 2}
    if language_preferences:
        group_scores.append(len(language_preferences & language_values) / len(language_preferences))

    steam_preferences = {str(item).casefold() for item in (*profile.preferred_genres, *profile.preferred_steam_tags)}
    mapping_is_reliable = _is_reliable_mapping(mapping)
    if steam_preferences:
        app_id = _steam_app_id(mapping) if mapping_is_reliable else None
        features = _steam_features_for(steam_features, str(trend.game_id), app_id)
        steam_values = _feature_values(features, "genres") | _feature_values(features, "tags")
        group_scores.append(len(steam_preferences & steam_values) / len(steam_preferences))
    return (sum(group_scores) / len(group_scores) if group_scores else 0.0), mapping_is_reliable


def _growth_signal(trend: GameTrend, history: object | None) -> tuple[float | None, bool]:
    historical_growth = _field(history, "growth_score", "growth", "growth_rate", default=_MISSING)
    if historical_growth is not _MISSING and historical_growth is not None:
        return _as_float(historical_growth), True
    trend_growth = _as_float(getattr(trend, "growth_score", None))
    if trend_growth is not None and abs(trend_growth) > 1e-9:
        return trend_growth, True
    if bool(getattr(trend, "growth_available", False)):
        return trend_growth or 0.0, True
    return None, False


def _momentum(value: float) -> float:
    normalized = value / 100.0 if abs(value) > 1 else value
    if normalized < 0:
        return _clamp(0.5 + normalized / 2.0)
    return _clamp(normalized)


def _trend_direction(value: float | None, available: bool) -> str:
    if not available or value is None:
        return "Unavailable"
    normalized = value / 100.0 if abs(value) > 1 else value
    if normalized > 0.05:
        return "Rising"
    if normalized < -0.05:
        return "Falling"
    return "Stable"


def _stability(trend: GameTrend, history: object | None) -> float:
    volatility = _as_float(_field(history, "volatility", default=None))
    consistency = _as_float(_field(history, "observation_consistency", "consistency", default=None))
    viewer_history = _field(history, "viewer_history", default=())
    try:
        values = [max(0, float(value)) for value in viewer_history]
    except TypeError:
        values = []
    if volatility is None and len(values) >= 2:
        mean = sum(values) / len(values)
        if mean > 0:
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            volatility = _clamp(math.sqrt(variance) / mean)
    if volatility is not None:
        stability = 1.0 - _clamp(volatility)
        if consistency is not None:
            stability = (stability + _clamp(consistency)) / 2.0
        return stability
    if consistency is not None:
        return _clamp(consistency)
    return 0.5 if max(0, int(getattr(trend, "channel_count", 0))) else 0.0


def _range_fit(value: float, low: float, high: float) -> float:
    if value <= 0:
        return 0.0
    if low <= value <= high:
        return 1.0
    if value < low:
        return _clamp(1.0 / (1.0 + math.log1p(low / max(value, 1.0))))
    return _clamp(1.0 / (1.0 + math.log1p(value / high)))


def _tier_suitability(viewers: int, channels: int, tier: str) -> float:
    viewer_range, channel_range = TIER_RANGES.get(tier.casefold(), TIER_RANGES["mid-size"])
    return _clamp(0.55 * _range_fit(viewers, *viewer_range) + 0.45 * _range_fit(channels, *channel_range))


def _confidence(
    trend: GameTrend,
    history: object | None,
    source_mode: str,
    observed_at: str | None,
    now: datetime | None,
) -> float:
    source_factors = {"live": 1.0, "fresh_snapshot": 0.75, "snapshot": 0.65, "manual": 0.60, "demo": 0.45, "fallback": 0.35}
    source_factor = source_factors.get(source_mode.casefold(), 0.40)
    rows = max(0, _as_int(getattr(trend, "contributing_stream_rows", 0)))
    coverage = _clamp(rows / 20.0) if rows else 0.20
    if bool(getattr(trend, "partial_coverage", False)):
        coverage *= 0.75
    observations = max(0, _as_int(_field(history, "observation_count", default=0)))
    history_factor = _clamp(observations / 10.0) if observations else 0.30
    consistency = _as_float(_field(history, "observation_consistency", default=None))
    if consistency is not None:
        history_factor = (history_factor + _clamp(consistency)) / 2.0
    if observed_at:
        try:
            reference = now or datetime.now(timezone.utc)
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
            age_hours = max(0.0, (reference - _parse_observed_at(observed_at)).total_seconds() / 3600)
            recency = 1.0 if age_hours <= 48 else 0.75 if age_hours <= 168 else 0.50 if age_hours <= 720 else 0.25
        except (TypeError, ValueError):
            recency = 0.25
    else:
        recency = 0.40
    return _clamp(0.30 * source_factor + 0.25 * coverage + 0.25 * history_factor + 0.20 * recency)


def _weights(strategy: str) -> dict[str, float]:
    return dict(STRATEGY_WEIGHTS.get(strategy.casefold(), DEFAULT_WEIGHTS))


def _score_components(components: OpportunityComponents, weights: dict[str, float], momentum_available: bool) -> float:
    values = components.values
    active_weights = {key: value for key, value in weights.items() if key != "momentum" or momentum_available}
    total_weight = sum(active_weights.values()) or 1.0
    return _clamp(sum(values[key] * weight for key, weight in active_weights.items()) / total_weight)


def _cautions(
    trend: GameTrend,
    components: OpportunityComponents,
    momentum_available: bool,
    trend_direction: str,
    source_mode: str,
    observed_at: str | None,
    now: datetime | None,
    mapping_is_reliable: bool,
) -> tuple[str, ...]:
    cautions: list[str] = []
    if max(0.0, float(getattr(trend, "top_one_viewer_share", 0.0))) >= 0.50 or max(0.0, float(getattr(trend, "top_five_viewer_share", 0.0))) >= 0.80:
        cautions.append("High viewer concentration means the category may depend on a few channels.")
    rows = max(0, _as_int(getattr(trend, "contributing_stream_rows", 0)))
    if rows < 5 or max(0, _as_int(getattr(trend, "channel_count", 0))) < MIN_VIABLE_CHANNELS:
        cautions.append("Limited observations make this opportunity directional.")
    if observed_at:
        try:
            reference = now or datetime.now(timezone.utc)
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
            age_hours = max(0.0, (reference - _parse_observed_at(observed_at)).total_seconds() / 3600)
            if age_hours > 48:
                cautions.append("Stale data may not reflect current category conditions.")
        except (TypeError, ValueError):
            cautions.append("Observation time could not be verified.")
    if not momentum_available:
        cautions.append("Momentum unavailable; other components were reweighted proportionally.")
    elif trend_direction == "Falling":
        cautions.append("Falling demand is a downside signal.")
    if components.competition < 0.35 and max(0, _as_int(getattr(trend, "channel_count", 0))) > 0:
        cautions.append("Heavy competition may make discovery difficult.")
    if not mapping_is_reliable:
        cautions.append("No verified Steam mapping; Steam preference evidence is unavailable.")
    if source_mode.casefold() == "demo":
        cautions.append("Demo-only evidence is illustrative and not a live Twitch observation.")
    if bool(getattr(trend, "partial_coverage", False)):
        cautions.append("Partial Twitch coverage may undercount the category.")
    return tuple(cautions)


def score_game_opportunities(
    trends: list[GameTrend] | Snapshot,
    profile: StreamerProfile,
    historical_features: Mapping[str, object] | None = None,
    verified_steam_mappings: Mapping[str, object] | None = None,
    steam_features: Mapping[object, object] | None = None,
    source_mode: str | None = None,
    observed_at: str | None = None,
    now: datetime | None = None,
) -> list[GameOpportunity]:
    """Rank categories for a streamer, keeping opportunity and evidence quality separate."""
    if isinstance(trends, Snapshot):
        snapshot = trends
        trends = snapshot.data
        source_mode = source_mode or snapshot.mode
        observed_at = observed_at or snapshot.observed_at
    if not trends:
        return []
    max_viewers = max(max(0, _as_int(getattr(item, "viewer_count", 0))) for item in trends) or 1
    max_channels = max(max(0, _as_int(getattr(item, "channel_count", 0))) for item in trends) or 1
    max_ratio = max(
        (
            max(0, _as_int(getattr(item, "viewer_count", 0)))
            / max(1, _as_int(getattr(item, "channel_count", 0)))
        )
        for item in trends
    ) or 1.0
    results: list[GameOpportunity] = []
    for trend in trends:
        game_id = str(getattr(trend, "game_id", ""))
        name = str(getattr(trend, "name", game_id))
        viewers = max(0, _as_int(getattr(trend, "viewer_count", 0)))
        channels = max(0, _as_int(getattr(trend, "channel_count", 0)))
        ratio = viewers / channels if channels else 0.0
        demand = _clamp(math.log1p(viewers) / math.log1p(max_viewers)) if viewers else 0.0
        if viewers < MIN_VIABLE_VIEWERS or channels < MIN_VIABLE_CHANNELS:
            reach = 0.0
        else:
            capped_ratio = min(REACH_RATIO_CAP, ratio)
            reach = _clamp(math.log1p(capped_ratio) / math.log1p(REACH_RATIO_CAP))
        channel_pressure = math.log1p(channels) / math.log1p(max_channels) if channels else 1.0
        competition = 0.0 if viewers < MIN_VIABLE_VIEWERS or channels < MIN_VIABLE_CHANNELS else _clamp(0.65 * reach + 0.35 * (1.0 - channel_pressure))
        history = _history_for(historical_features, game_id)
        growth_value, momentum_available = _growth_signal(trend, history)
        momentum = _momentum(growth_value) if momentum_available and growth_value is not None else 0.0
        stability = _stability(trend, history)
        mapping = _mapping_for(verified_steam_mappings, game_id)
        preference_fit, mapping_is_reliable = _preference_fit(trend, profile, mapping, steam_features)
        tier = _tier_suitability(viewers, channels, profile.channel_size_tier)
        components = OpportunityComponents(
            round(demand, 4), round(reach, 4), round(momentum, 4), round(competition, 4),
            round(preference_fit, 4), round(stability, 4), round(tier, 4),
        )
        score = round(_score_components(components, _weights(profile.strategy), momentum_available) * 100.0, 2)
        mode = str(source_mode or getattr(trend, "source_mode", "Unknown"))
        timestamp = observed_at or getattr(trend, "observed_at", None)
        direction = _trend_direction(growth_value, momentum_available)
        confidence = round(_confidence(trend, history, mode, timestamp, now), 4)
        reasons = [
            f"{viewers:,} observed viewers across {channels:,} channels",
            f"viewer-to-channel opportunity {ratio:.1f}",
        ]
        if direction != "Unavailable":
            reasons.append(f"trend direction is {direction.casefold()}")
        if preference_fit > 0:
            reasons.append("matches your genre, tag, or language preferences")
        if tier >= 0.75:
            reasons.append(f"fits the {profile.channel_size_tier.replace('-', ' ')} channel range")
        results.append(GameOpportunity(
            game_id,
            name,
            score,
            tuple(reasons),
            viewers,
            channels,
            score_band(score),
            components,
            round(ratio, 2),
            _cautions(trend, components, momentum_available, direction, mode, timestamp, now, mapping_is_reliable),
            direction,
            confidence,
            confidence_band(confidence),
            mode,
            timestamp,
            _steam_app_id(mapping) if mapping_is_reliable else None,
        ))
    results.sort(key=lambda item: (-item.score, item.name.casefold(), item.game_id))
    return results

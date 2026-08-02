"""Explainable developer-to-streamer fit ranking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from statistics import median
from typing import Iterable, Mapping


FIT_WEIGHTS = {
    "category_history_fit": 0.25,
    "similar_game_fit": 0.20,
    "audience_suitability": 0.15,
    "consistency": 0.10,
    "momentum": 0.10,
    "language_fit": 0.10,
    "discoverability": 0.05,
    "data_confidence": 0.05,
}

AUDIENCE_RANGES = {
    "emerging": (100, 5_000),
    "mid-size": (1_000, 20_000),
    "large": (5_000, 100_000),
}

# These floors are derived from the same audience ranges used by fit scoring.
# The ranges intentionally overlap for suitability scoring; classification is
# deterministic by assigning each viewer count to the highest matching floor.
CREATOR_TIER_ORDER = ("emerging", "mid-size", "large")
CREATOR_TIER_THRESHOLDS = {
    tier: AUDIENCE_RANGES[tier][0]
    for tier in CREATOR_TIER_ORDER
}
MIN_CREATOR_TIER_HISTORY = 3


def normalize_creator_tier(value: object) -> str:
    """Return a canonical creator tier, or ``unknown`` for invalid values."""

    normalized = str(value or "").strip().casefold().replace("_", "-").replace(" ", "-")
    return normalized if normalized in CREATOR_TIER_THRESHOLDS else "unknown"


def classify_creator_tier(
    viewer_value: object,
    observation_count: int | None = None,
    history: Iterable[object] | None = None,
) -> str:
    """Classify a creator into a directional audience-size band.

    Thresholds are shared with ``AUDIENCE_RANGES``: fewer than 100 viewers is
    ``unknown``; 100-999 is ``emerging``; 1,000-4,999 is ``mid-size``; and
    5,000 or more is ``large``. With at least three valid historical viewer
    observations, the median is used; otherwise the supplied current or
    average value is used. Missing and non-positive values remain unknown.
    """

    def positive_number(value: object) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number) or number <= 0:
            return None
        return number

    history_values = tuple(
        number
        for number in (positive_number(value) for value in (history or ()))
        if number is not None
    )
    try:
        count = None if observation_count is None else max(0, int(observation_count))
    except (TypeError, ValueError):
        count = 0
    candidate = (
        float(median(history_values))
        if len(history_values) >= MIN_CREATOR_TIER_HISTORY
        and (count is None or count >= MIN_CREATOR_TIER_HISTORY)
        else positive_number(viewer_value)
    )
    if candidate is None:
        return "unknown"
    for tier in reversed(CREATOR_TIER_ORDER):
        if candidate >= CREATOR_TIER_THRESHOLDS[tier]:
            return tier
    return "unknown"


@dataclass(frozen=True)
class PromotionCampaignProfile:
    """Campaign inputs for directional creator selection.

    This profile describes fit evidence only. It does not model sales,
    conversion, sponsorship pricing, or guaranteed campaign outcomes.
    """

    game_name: str
    steam_app_id: int | None = None
    genres: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    similar_games: tuple[str, ...] = ()
    target_languages: tuple[str, ...] = ()
    preferred_streamer_tiers: tuple[str, ...] = ()
    budget_tier: str | None = None
    promotion_objective: str = "awareness"


@dataclass(frozen=True)
class StreamerProfile:
    """Current streamer data plus optional aggregate observation features."""

    streamer_id: str
    categories: set[str]
    language: str
    tier: str
    average_viewers: int
    name: str = ""
    category_history: tuple[str, ...] = ()
    similar_game_history: tuple[str, ...] = ()
    median_viewers: float | None = None
    peak_viewers: float | None = None
    primary_category: str | None = None
    primary_category_share: float | None = None
    viewer_volatility: float | None = None
    observation_count: int = 0
    seven_day_growth: float | None = None
    languages: tuple[str, ...] = ()
    source_mode: str = "Unknown"
    observed_at: str | None = None
    partial_coverage: bool = False
    profile_image_url: str | None = None
    twitch_channel_url: str | None = None
    login_name: str | None = None
    profile_image: str | None = None
    channel_url: str | None = None
    source_name: str = ""
    provenance_note: str = ""
    collection_ids: tuple[str, ...] = ()
    seven_day_growth_interval_hours: float | None = None
    seven_day_growth_baseline_at: str | None = None
    seven_day_growth_latest_at: str | None = None

    def __post_init__(self) -> None:
        normalized_tier = normalize_creator_tier(self.tier)
        if normalized_tier != "unknown":
            if normalized_tier != self.tier:
                object.__setattr__(self, "tier", normalized_tier)
            return
        viewer_value = self.median_viewers if self.median_viewers is not None else self.average_viewers
        derived_tier = classify_creator_tier(viewer_value, self.observation_count)
        object.__setattr__(self, "tier", derived_tier)


@dataclass(frozen=True)
class FitComponents:
    category_history_fit: float = 0.0
    similar_game_fit: float = 0.0
    audience_suitability: float = 0.0
    consistency: float = 0.0
    momentum: float = 0.0
    language_fit: float = 0.0
    discoverability: float = 0.0
    data_confidence: float = 0.0

    @property
    def values(self) -> dict[str, float]:
        return {
            "category_history_fit": self.category_history_fit,
            "similar_game_fit": self.similar_game_fit,
            "audience_suitability": self.audience_suitability,
            "consistency": self.consistency,
            "momentum": self.momentum,
            "language_fit": self.language_fit,
            "discoverability": self.discoverability,
            "data_confidence": self.data_confidence,
        }

    @property
    def category_fit(self) -> float:
        return self.category_history_fit

    @property
    def similar_fit(self) -> float:
        return self.similar_game_fit

    @property
    def category_history(self) -> float:
        return self.category_history_fit

    @property
    def similar_game(self) -> float:
        return self.similar_game_fit

    @property
    def audience(self) -> float:
        return self.audience_suitability

    @property
    def language(self) -> float:
        return self.language_fit


@dataclass(frozen=True)
class StreamerFit:
    streamer_id: str
    score: float
    reasons: tuple[str, ...]
    score_band: str = "Low fit"
    cautions: tuple[str, ...] = ()
    components: FitComponents = FitComponents()
    average_viewers: float | None = None
    median_viewers: float | None = None
    peak_viewers: float | None = None
    primary_category: str | None = None
    primary_category_share: float | None = None
    language: str | None = None
    channel_tier: str | None = None
    seven_day_growth: float | None = None
    confidence_score: float = 0.0
    confidence_band: str = "Very low confidence"
    profile_image_url: str | None = None
    twitch_channel_url: str | None = None
    streamer_name: str = ""
    unavailable_components: tuple[str, ...] = ()
    source_mode: str = "Unknown"
    observed_at: str | None = None
    partial_coverage: bool = False
    source_name: str = ""
    provenance_note: str = ""
    collection_ids: tuple[str, ...] = ()
    seven_day_growth_interval_hours: float | None = None
    seven_day_growth_baseline_at: str | None = None
    seven_day_growth_latest_at: str | None = None
    data_source: str = ""
    data_limitations: tuple[str, ...] = ()
    similar_game_matches: tuple[str, ...] = ()
    direct_game_matches: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return self.streamer_name

    @property
    def tier(self) -> str | None:
        return self.channel_tier


def _score_band(score: float) -> str:
    if score >= 75:
        return "Strong fit"
    if score >= 50:
        return "Promising fit"
    return "Low fit"


def _confidence_band(score: float) -> str:
    if score >= 0.80:
        return "High confidence"
    if score >= 0.55:
        return "Moderate confidence"
    if score >= 0.30:
        return "Low confidence"
    return "Very low confidence"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _values(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(str(key) for key in value)
    try:
        return tuple(str(item) for item in value if str(item).strip())
    except TypeError:
        return ()


def _campaign(game: PromotionCampaignProfile | Mapping[str, object]) -> PromotionCampaignProfile:
    if isinstance(game, PromotionCampaignProfile):
        return game
    languages = game.get("target_languages", game.get("languages", ()))
    if not languages and game.get("language"):
        languages = (game["language"],)
    return PromotionCampaignProfile(
        game_name=str(game.get("game_name", game.get("name", ""))),
        steam_app_id=game.get("steam_app_id"),
        genres=_values(game.get("genres", ())),
        tags=_values(game.get("tags", ())),
        similar_games=_values(game.get("similar_games", ())),
        target_languages=_values(languages),
        preferred_streamer_tiers=_values(game.get("preferred_streamer_tiers", game.get("preferred_tiers", ()))),
        budget_tier=str(game["budget_tier"]) if game.get("budget_tier") is not None else None,
        promotion_objective=str(game.get("promotion_objective", game.get("objective", "awareness"))),
    )


def _history_values(streamer: StreamerProfile) -> tuple[str, ...]:
    return streamer.category_history or tuple(str(value) for value in streamer.categories)


def _direct_game_matches(campaign: PromotionCampaignProfile, streamer: StreamerProfile) -> tuple[str, ...]:
    target = _normalized(campaign.game_name)
    if not target:
        return ()
    matches: list[str] = []
    seen: set[str] = set()
    for value in _history_values(streamer):
        display = str(value).strip()
        normalized = _normalized(display)
        if normalized == target and normalized not in seen:
            seen.add(normalized)
            matches.append(display)
    return tuple(matches)


def _category_history_fit(campaign: PromotionCampaignProfile, streamer: StreamerProfile) -> tuple[float, bool, int]:
    desired = {_normalized(value) for value in (campaign.game_name, *campaign.genres, *campaign.tags) if _normalized(value)}
    history = {_normalized(value) for value in _history_values(streamer) if _normalized(value)}
    if not desired or not history:
        return 0.0, False, 0
    overlap = desired & history
    return len(overlap) / len(desired), True, len(overlap)


def _similar_game_matches(campaign: PromotionCampaignProfile, streamer: StreamerProfile) -> tuple[str, ...]:
    desired: list[tuple[str, str]] = []
    seen: set[str] = set()
    for value in campaign.similar_games:
        normalized = _normalized(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            desired.append((normalized, str(value).strip()))
    history = streamer.similar_game_history or streamer.category_history
    observed = {_normalized(value) for value in history if _normalized(value)}
    return tuple(display for normalized, display in desired if normalized in observed)


def _similar_game_fit(campaign: PromotionCampaignProfile, streamer: StreamerProfile) -> tuple[float, bool]:
    desired = {_normalized(value) for value in campaign.similar_games if _normalized(value)}
    matches = _similar_game_matches(campaign, streamer)
    if not desired or not matches:
        return 0.0, False
    return len(matches) / len(desired), True


def _range_fit(value: float, low: float, high: float) -> float:
    if value <= 0:
        return 0.0
    if low <= value <= high:
        return 1.0
    if value < low:
        return _clamp(1.0 / (1.0 + math.log1p(low / max(value, 1.0))))
    return _clamp(1.0 / (1.0 + math.log1p(value / high)))


def _audience_suitability(campaign: PromotionCampaignProfile, streamer: StreamerProfile) -> tuple[float, bool]:
    viewer_value = streamer.median_viewers if streamer.median_viewers is not None else streamer.average_viewers
    if viewer_value is None or viewer_value <= 0:
        return 0.0, False
    preferred = tuple(str(value).casefold() for value in campaign.preferred_streamer_tiers)
    target_tiers = preferred or (streamer.tier.casefold(),)
    fits = []
    for tier in target_tiers:
        low, high = AUDIENCE_RANGES.get(tier, AUDIENCE_RANGES["mid-size"])
        fits.append(_range_fit(float(viewer_value), low, high))
    fit = max(fits, default=0.0)
    if preferred and streamer.tier.casefold() not in preferred:
        fit *= 0.25
    return fit, True


def _consistency(streamer: StreamerProfile) -> tuple[float, bool, tuple[str, ...]]:
    values: list[float] = []
    missing: list[str] = []
    if streamer.median_viewers is not None:
        average = max(1.0, float(streamer.average_viewers))
        values.append(_clamp(float(streamer.median_viewers) / average))
    else:
        missing.append("median viewers")
    if streamer.viewer_volatility is not None:
        values.append(1.0 - _clamp(float(streamer.viewer_volatility)))
    else:
        missing.append("viewer volatility")
    if streamer.observation_count > 0:
        values.append(_clamp(streamer.observation_count / 10.0))
    else:
        missing.append("observation count")
    if streamer.primary_category_share is not None:
        values.append(_clamp(float(streamer.primary_category_share)))
    else:
        missing.append("primary-category share")
    if not values:
        return 0.0, False, tuple(missing)
    return sum(values) / len(values), True, tuple(missing)


def _momentum(streamer: StreamerProfile) -> tuple[float, bool]:
    if streamer.seven_day_growth is None:
        return 0.0, False
    growth = float(streamer.seven_day_growth)
    if abs(growth) > 1:
        growth /= 100.0
    return _clamp(0.5 + growth / 2.0), True


def _language_fit(campaign: PromotionCampaignProfile, streamer: StreamerProfile) -> tuple[float, bool, str]:
    targets = {_normalized(value) for value in campaign.target_languages if _normalized(value)}
    if not targets:
        return 0.0, False, "no target languages"
    languages = {_normalized(streamer.language)} if streamer.language else set()
    languages |= {_normalized(value) for value in streamer.languages if _normalized(value)}
    if not languages:
        return 0.0, False, "streamer language is missing"
    if languages & targets:
        return 1.0, True, ""
    return 0.0, True, "target language mismatch"


def _discoverability(campaign: PromotionCampaignProfile, streamer: StreamerProfile) -> tuple[float, bool]:
    viewer_value = streamer.median_viewers if streamer.median_viewers is not None else streamer.average_viewers
    if viewer_value is None or viewer_value <= 0:
        return 0.0, False
    target_tiers = tuple(str(value).casefold() for value in campaign.preferred_streamer_tiers) or ("mid-size",)
    range_score = max(
        (_range_fit(float(viewer_value), *AUDIENCE_RANGES.get(tier, AUDIENCE_RANGES["mid-size"])) for tier in target_tiers),
        default=0.0,
    )
    meaningful_reach = math.log1p(min(float(viewer_value), 100_000)) / math.log1p(100_000)
    return _clamp(0.65 * range_score + 0.35 * meaningful_reach), True


def _freshness_score(observed_at: str | None, now: datetime | None) -> float:
    if not observed_at:
        return 0.40
    try:
        parsed = datetime.fromisoformat(str(observed_at).strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (reference - parsed).total_seconds() / 3600)
    except (TypeError, ValueError):
        return 0.20
    if age_hours <= 48:
        return 1.0
    if age_hours <= 168:
        return 0.75
    if age_hours <= 720:
        return 0.50
    return 0.25


def _data_confidence(streamer: StreamerProfile, now: datetime | None) -> float:
    source_factors = {
        "live": 1.0,
        "fresh_snapshot": 0.75,
        "cached/snapshot": 0.60,
        "snapshot": 0.60,
        "cached": 0.60,
        "manual": 0.60,
        "historical": 0.60,
        "demo": 0.45,
        "fallback": 0.30,
        "mixed": 0.42,
    }
    source = source_factors.get(str(streamer.source_mode).casefold(), 0.35)
    observations = _clamp(streamer.observation_count / 10.0) if streamer.observation_count else 0.15
    freshness = _freshness_score(streamer.observed_at, now)
    coverage = 0.75 if streamer.partial_coverage else 1.0
    return _clamp(0.35 * source + 0.30 * observations + 0.25 * freshness + 0.10 * coverage)


def _active_score(components: FitComponents, available: Mapping[str, bool]) -> float:
    values = components.values
    active_weights = {key: weight for key, weight in FIT_WEIGHTS.items() if available.get(key, False)}
    total_weight = sum(active_weights.values())
    if not total_weight:
        return 0.0
    return _clamp(sum(values[key] * weight for key, weight in active_weights.items()) / total_weight) * 100.0


def _cautions(
    campaign: PromotionCampaignProfile,
    streamer: StreamerProfile,
    available: Mapping[str, bool],
    consistency_missing: tuple[str, ...],
    language_note: str,
    now: datetime | None,
) -> tuple[str, ...]:
    labels = {
        "category_history_fit": "Category history fit",
        "similar_game_fit": "Similar-game fit",
        "audience_suitability": "Audience suitability",
        "consistency": "Consistency",
        "momentum": "Momentum",
        "language_fit": "Language fit",
        "discoverability": "Discoverability",
    }
    cautions = [
        f"{labels[key]} unavailable; remaining components were reweighted proportionally."
        for key, is_available in available.items()
        if key != "data_confidence" and not is_available
    ]
    if consistency_missing and available.get("consistency"):
        cautions.append("Consistency is based on incomplete history: " + ", ".join(consistency_missing) + ".")
    if language_note == "streamer language is missing":
        cautions.append("Streamer language is missing; a missing language is not treated as a match.")
    elif language_note == "target language mismatch":
        cautions.append("Streamer language does not match the campaign target languages.")
    if streamer.observation_count < 3:
        cautions.append("Limited observations reduce confidence in the fit.")
    if streamer.partial_coverage:
        cautions.append("Partial coverage may understate or distort the streamer history.")
    if streamer.observed_at and _freshness_score(streamer.observed_at, now) < 0.5:
        cautions.append("Stale observations reduce confidence in the fit.")
    source_mode = str(streamer.source_mode).casefold()
    if source_mode == "demo":
        cautions.append("Demo-only evidence is illustrative, not a live creator history.")
    if source_mode == "fallback":
        cautions.append("Fallback evidence is cached recovery data and lowers confidence.")
    if source_mode == "historical":
        cautions.append("Historical observations may not reflect current creator activity.")
    if source_mode == "mixed":
        cautions.append("Mixed-source evidence combines collections with different provenance quality.")
    if streamer.provenance_note:
        cautions.append(streamer.provenance_note)
    if campaign.budget_tier:
        cautions.append("Budget tier is recorded for context; sponsorship prices are not estimated.")
    cautions.append("This is directional public-signal fit, not a sales or conversion prediction.")
    return tuple(cautions)


def _reasons(
    campaign: PromotionCampaignProfile,
    streamer: StreamerProfile,
    components: FitComponents,
    category_overlap: int,
    language_note: str,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if category_overlap:
        reasons.append(f"shares {category_overlap} historical game/category signal(s)")
    if (
        (streamer.primary_category and _normalized(streamer.primary_category) == _normalized(campaign.game_name))
        or _normalized(campaign.game_name) in {_normalized(value) for value in _history_values(streamer)}
    ):
        reasons.append(f"matches {campaign.game_name} category")
    if components.similar_game_fit:
        reasons.append("has observed history with a comparable game")
    if components.audience_suitability >= 0.70:
        reasons.append(f"audience size fits the campaign's preferred streamer range")
    if components.language_fit > 0:
        reasons.append(f"matches a target campaign language ({streamer.language})")
    if components.momentum >= 0.65:
        reasons.append("recent seven-day growth is positive")
    if components.consistency >= 0.70:
        reasons.append("viewer history is relatively consistent")
    if not reasons:
        reasons.append("fit is based on limited available public signals")
    return tuple(reasons)


def _channel_url(streamer: StreamerProfile) -> str | None:
    if streamer.twitch_channel_url or streamer.channel_url:
        return streamer.twitch_channel_url or streamer.channel_url
    if streamer.login_name:
        return f"https://twitch.tv/{streamer.login_name}"
    return None


def rank_streamers(
    game: PromotionCampaignProfile | Mapping[str, object],
    streamers: list[StreamerProfile],
    tier: str | None = None,
    now: datetime | None = None,
) -> list[StreamerFit]:
    """Rank creators for a campaign using aggregate history and evidence quality."""
    campaign = _campaign(game)
    output: list[StreamerFit] = []
    for streamer in streamers:
        if tier and streamer.tier.casefold() != str(tier).casefold():
            continue
        category_fit, category_available, category_overlap = _category_history_fit(campaign, streamer)
        direct_game_matches = _direct_game_matches(campaign, streamer)
        similar_game_matches = _similar_game_matches(campaign, streamer)
        similar_fit, similar_available = _similar_game_fit(campaign, streamer)
        audience_fit, audience_available = _audience_suitability(campaign, streamer)
        consistency, consistency_available, consistency_missing = _consistency(streamer)
        momentum, momentum_available = _momentum(streamer)
        language_fit, language_available, language_note = _language_fit(campaign, streamer)
        discoverability, discoverability_available = _discoverability(campaign, streamer)
        data_confidence = _data_confidence(streamer, now)
        components = FitComponents(
            round(category_fit, 4),
            round(similar_fit, 4),
            round(audience_fit, 4),
            round(consistency, 4),
            round(momentum, 4),
            round(language_fit, 4),
            round(discoverability, 4),
            round(data_confidence, 4),
        )
        available = {
            "category_history_fit": category_available,
            "similar_game_fit": similar_available,
            "audience_suitability": audience_available,
            "consistency": consistency_available,
            "momentum": momentum_available,
            "language_fit": language_available,
            "discoverability": discoverability_available,
            "data_confidence": True,
        }
        score = round(_active_score(components, available), 1)
        confidence = round(data_confidence, 4)
        limitations = _cautions(campaign, streamer, available, consistency_missing, language_note, now)
        output.append(StreamerFit(
            streamer_id=streamer.streamer_id,
            score=score,
            reasons=_reasons(campaign, streamer, components, category_overlap, language_note),
            score_band=_score_band(score),
            cautions=limitations,
            components=components,
            average_viewers=streamer.average_viewers,
            median_viewers=streamer.median_viewers,
            peak_viewers=streamer.peak_viewers,
            primary_category=streamer.primary_category,
            primary_category_share=streamer.primary_category_share,
            language=streamer.language,
            channel_tier=streamer.tier,
            seven_day_growth=streamer.seven_day_growth,
            confidence_score=confidence,
            confidence_band=_confidence_band(confidence),
            profile_image_url=streamer.profile_image_url or streamer.profile_image,
            twitch_channel_url=_channel_url(streamer),
            streamer_name=streamer.name or streamer.streamer_id,
            unavailable_components=tuple(key for key, is_available in available.items() if not is_available),
            source_mode=streamer.source_mode,
            observed_at=streamer.observed_at,
            partial_coverage=streamer.partial_coverage,
            source_name=streamer.source_name,
            provenance_note=streamer.provenance_note,
            collection_ids=streamer.collection_ids,
            seven_day_growth_interval_hours=streamer.seven_day_growth_interval_hours,
            seven_day_growth_baseline_at=streamer.seven_day_growth_baseline_at,
            seven_day_growth_latest_at=streamer.seven_day_growth_latest_at,
            data_source=streamer.source_mode,
            data_limitations=limitations,
            similar_game_matches=similar_game_matches,
            direct_game_matches=direct_game_matches,
        ))
    output.sort(key=lambda item: (-item.score, -item.confidence_score, item.streamer_name.casefold(), item.streamer_id))
    return output

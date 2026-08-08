"""Explainable developer-to-creator fit ranking across normalized providers."""

from __future__ import annotations

from dataclasses import dataclass
import re

from gamepulse.providers.contracts import CreatorSignal
from gamepulse.streamer_opportunity import renormalized_weighted_score


@dataclass(frozen=True)
class StreamerProfile:
    """Compatibility profile retained for older callers.

    New Developer Mode code should pass ``CreatorSignal`` records directly to
    ``rank_creators``.
    """

    streamer_id: str
    categories: set[str]
    language: str
    tier: str
    average_viewers: int


@dataclass(frozen=True)
class StreamerFit:
    streamer_id: str
    score: float
    reasons: tuple[str, ...]
    score_band: str = "Low fit"
    creator_name: str = ""
    platform: str = "Unknown"
    source_mode: str = "Unknown"
    source_name: str = ""
    observed_at: str = ""
    confidence: str = "unknown"
    audience_value: float | None = None
    audience_metric: str | None = None
    profile_url: str | None = None
    unavailable_components: tuple[str, ...] = ()

    @property
    def creator_id(self) -> str:
        return self.streamer_id


CreatorFit = StreamerFit


def _score_band(score: float) -> str:
    if score >= 75:
        return "Strong fit"
    if score >= 50:
        return "Promising fit"
    return "Low fit"


def _normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _legacy_creator(profile: StreamerProfile) -> CreatorSignal:
    return CreatorSignal(
        creator_id=profile.streamer_id,
        name=profile.streamer_id,
        platform="Unknown",
        profile_url=None,
        game_id=None,
        game_name=None,
        audience_value=float(max(0, profile.average_viewers)),
        audience_metric="avg_viewers",
        language=profile.language,
        channel_size_tier=profile.tier,
        tags=tuple(sorted(profile.categories)),
        games=(),
        observed_at="",
        source_name="Legacy creator profile",
        confidence="unknown",
        source_mode="Imported",
    )


def _audience_suitability(value: float | None, tier: str | None) -> float | None:
    if value is None or not tier:
        return None
    ranges = {
        "emerging": (50.0, 1000.0),
        "mid-size": (500.0, 5000.0),
        "large": (3000.0, 100000.0),
    }
    low, high = ranges.get(tier.casefold(), ranges["mid-size"])
    number = max(0.0, float(value))
    if low <= number <= high:
        return 1.0
    if number < low:
        return max(0.0, number / low)
    return max(0.0, min(1.0, high / number))


def rank_creators(
    game: dict,
    creators: list[CreatorSignal],
    tier: str | None = None,
    language: str | None = None,
) -> list[CreatorFit]:
    """Rank creator records without assuming a Twitch origin."""

    game_name = str(game.get("name") or "")
    desired_tags = {
        _normalized(value)
        for value in set(game.get("genres", set())) | set(game.get("tags", set()))
        if _normalized(value)
    }
    target_language = str(language or game.get("language") or "").casefold().strip()
    weights = {
        "selected_game_history": 0.35,
        "category_fit": 0.30,
        "language_fit": 0.15,
        "audience_suitability": 0.10,
        "tier_fit": 0.10,
    }

    output: list[CreatorFit] = []
    for creator in creators:
        creator_tier = str(creator.channel_size_tier or "unknown").casefold()
        if tier and creator_tier != tier.casefold():
            continue

        creator_games = {_normalized(value) for value in creator.games if _normalized(value)}
        if creator.game_name:
            creator_games.add(_normalized(creator.game_name))
        selected_game_history = None if not game_name or not creator_games else (1.0 if _normalized(game_name) in creator_games else 0.0)

        creator_tags = {_normalized(value) for value in creator.tags if _normalized(value)}
        category_fit = None
        if desired_tags:
            category_fit = len(desired_tags & creator_tags) / len(desired_tags) if creator_tags else 0.0

        language_fit = None
        if target_language:
            language_fit = 1.0 if creator.language.casefold() == target_language else 0.0

        audience_suitability = _audience_suitability(creator.audience_value, tier)
        tier_fit = None if not tier else (1.0 if creator_tier == tier.casefold() else 0.0)
        components = {
            "selected_game_history": selected_game_history,
            "category_fit": category_fit,
            "language_fit": language_fit,
            "audience_suitability": audience_suitability,
            "tier_fit": tier_fit,
        }
        score = round(renormalized_weighted_score(components, weights) * 100.0, 1)
        unavailable = tuple(name for name, value in components.items() if value is None)

        reasons: list[str] = []
        if selected_game_history == 1.0:
            reasons.append(f"lists {game_name} in creator history")
        if category_fit:
            overlap = len(desired_tags & creator_tags)
            reasons.append(f"shares {overlap} genre/tag signal(s)")
        if language_fit == 1.0:
            reasons.append(f"matches {creator.language} language")
        if tier and creator_tier == tier.casefold():
            reasons.append(f"matches the requested {tier} creator tier")
        if creator.audience_value is not None:
            reasons.append(f"reported audience signal: {creator.audience_value:,.0f} {str(creator.audience_metric or 'audience').replace('_', ' ')}")
        else:
            reasons.append("audience size is unavailable and was excluded from fit scoring")
        reasons.append(f"source: {creator.source_mode} · {creator.source_name}")

        output.append(
            CreatorFit(
                streamer_id=creator.creator_id,
                creator_name=creator.name,
                score=score,
                reasons=tuple(reasons),
                score_band=_score_band(score),
                platform=creator.platform,
                source_mode=creator.source_mode,
                source_name=creator.source_name,
                observed_at=creator.observed_at,
                confidence=creator.confidence,
                audience_value=creator.audience_value,
                audience_metric=creator.audience_metric,
                profile_url=creator.profile_url,
                unavailable_components=unavailable,
            )
        )
    output.sort(key=lambda item: (-item.score, item.creator_name.casefold(), item.streamer_id))
    return output


def rank_streamers(game: dict, streamers: list[StreamerProfile | CreatorSignal], tier: str | None = None) -> list[StreamerFit]:
    """Backward-compatible wrapper around source-neutral creator ranking."""

    creators = [item if isinstance(item, CreatorSignal) else _legacy_creator(item) for item in streamers]
    return rank_creators(game, creators, tier=tier)

"""Explainable developer-to-streamer fit ranking."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamerProfile:
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


def _score_band(score: float) -> str:
    if score >= 75:
        return "Strong fit"
    if score >= 50:
        return "Promising fit"
    return "Low fit"


def rank_streamers(game: dict, streamers: list[StreamerProfile], tier: str | None = None) -> list[StreamerFit]:
    desired = {str(value).casefold() for value in game.get("genres", set()) | game.get("tags", set())}
    output = []
    for streamer in streamers:
        if tier and streamer.tier != tier:
            continue
        overlap = len(desired & {value.casefold() for value in streamer.categories})
        category_fit = overlap / len(desired) if desired else 0.0
        language_fit = 1 if not game.get("language") or streamer.language.casefold() == str(game["language"]).casefold() else 0
        viewer_fit = 1 / (1 + max(0, streamer.average_viewers) / 1000)
        score = (category_fit * 0.55 + language_fit * 0.2 + viewer_fit * 0.25) * 100
        reasons = []
        if overlap:
            reasons.append(f"shares {overlap} genre/tag signal(s)")
        if language_fit:
            reasons.append(f"matches {streamer.language} language")
        reasons.append(f"{streamer.tier} channel with about {streamer.average_viewers:,} average viewers")
        output.append(StreamerFit(streamer.streamer_id, round(score, 1), tuple(reasons), _score_band(score)))
    output.sort(key=lambda item: (-item.score, item.streamer_id))
    return output

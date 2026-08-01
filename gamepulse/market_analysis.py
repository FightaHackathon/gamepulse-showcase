"""Public Steam market signals and explicitly estimated scenarios."""

from __future__ import annotations

from dataclasses import dataclass
import math
import sqlite3
from pathlib import Path

from gamepulse.forecasting import ForecastRange
from gamepulse.review_analysis import ReviewAnalysis


@dataclass(frozen=True)
class MarketSnapshot:
    steam_app_id: int
    seller_rank: int | None
    owners_low: int | None
    owners_high: int | None
    price_usd: float | None
    total_reviews: int | None
    peak_ccu: int | None
    source_mode: str
    source_name: str
    observed_at: str
    source_url: str | None = None
    collection_method: str = "public endpoint responses"
    confidence: str = "unknown"
    discount_pct: float | None = None
    player_metric: str = "peak"


@dataclass(frozen=True)
class MarketAnalysis:
    seller_rank: int | None
    estimated_gross_low: float | None
    estimated_gross_high: float | None
    comparable_games: tuple[dict, ...]
    disclaimer: str


@dataclass(frozen=True)
class DeveloperOpportunityComponents:
    """Normalized public signals used by the Developer Mode score."""

    audience: float
    review_health: float
    momentum: float
    creator_fit: float
    comparable_coverage: float

    def __len__(self) -> int:
        return 5


@dataclass(frozen=True)
class DeveloperOpportunity:
    """Directional opportunity signal for the prototype dashboard."""

    score: int
    score_band: str
    components: DeveloperOpportunityComponents
    reasons: tuple[str, ...]
    disclaimer: str


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 3)


def _audience_signal(snapshot: MarketSnapshot) -> tuple[float, bool]:
    if snapshot.owners_high and snapshot.owners_high > 0:
        return _bounded(math.log10(snapshot.owners_high + 1) / 7.0), True
    if snapshot.peak_ccu and snapshot.peak_ccu > 0:
        return _bounded(math.log10(snapshot.peak_ccu + 1) / 5.0), True
    return 0.0, False


def analyze_developer_opportunity(
    snapshot: MarketSnapshot,
    review_analysis: ReviewAnalysis,
    forecast: ForecastRange,
    creator_count: int,
    comparable_count: int,
    creator_scores: tuple[float, ...] | list[float] | None = None,
) -> DeveloperOpportunity:
    """Combine available public signals into an explainable 0–100 score."""
    audience, audience_available = _audience_signal(snapshot)
    review_health = _bounded(review_analysis.positive_ratio) if review_analysis.review_count else 0.0
    review_available = review_analysis.review_count > 0
    if review_analysis.review_count and forecast.expected > 0:
        momentum = _bounded((forecast.expected / review_analysis.review_count) * 12.0)
        momentum_available = True
    else:
        momentum = 0.0
        momentum_available = False
    observed_creator_count = len(creator_scores) if creator_scores is not None else max(0, creator_count)
    if creator_scores:
        creator_fit = _bounded(sum(_bounded(float(score) / 100.0) for score in creator_scores) / len(creator_scores))
    else:
        creator_fit = _bounded(max(0, creator_count) / 5.0)
    comparable_coverage = _bounded(max(0, comparable_count) / 5.0)

    components = DeveloperOpportunityComponents(audience, review_health, momentum, creator_fit, comparable_coverage)
    weighted = (
        audience * 0.30
        + review_health * 0.20
        + momentum * 0.20
        + creator_fit * 0.15
        + comparable_coverage * 0.15
    )
    score = round(weighted * 100)
    band = "Strong signal" if score >= 75 else "Promising signal" if score >= 50 else "Early signal"
    reasons = (
        "Public audience signal is available from owner or CCU estimates." if audience_available else "Public audience signal is unavailable.",
        "Review health is visible from collected recommendations." if review_available else "Review health is unavailable because no reviews were collected.",
        "Review momentum is estimated from the recent activity baseline." if momentum_available else "Review momentum is unavailable because there is not enough activity history.",
        f"Creator coverage includes {observed_creator_count:,} observed Twitch profiles with an average fit of {creator_fit:.0%}." if observed_creator_count else "Creator coverage is unavailable in the current Twitch snapshot.",
        f"The catalog provides {max(0, comparable_count):,} comparable game signals." if comparable_count else "Comparable-game coverage is unavailable from shared tags or genres.",
    )
    return DeveloperOpportunity(
        score=score,
        score_band=band,
        components=components,
        reasons=reasons,
        disclaimer="Opportunity score is a directional public-signal estimate, not verified sales, downloads, or a revenue forecast.",
    )


def latest_market_snapshot(database_path: Path, app_id: int) -> MarketSnapshot | None:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM steam_market_snapshots WHERE steam_app_id = ? ORDER BY observed_at DESC LIMIT 1",
            (app_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return MarketSnapshot(
        steam_app_id=int(row["steam_app_id"]), seller_rank=row["seller_rank"], owners_low=row["owners_low"],
        owners_high=row["owners_high"], price_usd=row["price_usd"], total_reviews=row["total_reviews"],
        peak_ccu=row["peak_ccu"], source_mode=row["source_mode"], source_name=row["source_name"],
        observed_at=row["observed_at"], source_url=row["source_url"],
        collection_method=row["collection_method"] or "unknown", confidence=row["confidence"] or "unknown",
        discount_pct=float(row["discount_pct"]) if row["discount_pct"] is not None else None,
        player_metric=(row["player_metric"] or "peak") if "player_metric" in row.keys() else ("current" if "current players" in str(row["source_name"]).casefold() else "peak"),
    )


def analyze_market(snapshot: MarketSnapshot, comparable_games: list[dict]) -> MarketAnalysis:
    if snapshot.owners_low is None or snapshot.owners_high is None or snapshot.price_usd is None:
        low = high = None
    else:
        low = round(snapshot.owners_low * snapshot.price_usd, 2)
        high = round(snapshot.owners_high * snapshot.price_usd, 2)
    return MarketAnalysis(snapshot.seller_rank, low, high, tuple(comparable_games), "Ownership and gross revenue are estimated from public signals, not verified Steam sales; seller rank is a verified relative ranking only.")

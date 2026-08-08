"""Pure, source-neutral developer estimates built from prepared signals.

The values in this module are deliberately scenarios.  SteamSpy owner ranges
are third-party estimates, and neither the owner range nor the revenue values
represent verified sales data.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DeveloperPredictionInput:
    """Primitive inputs used to calculate a developer prediction."""

    steamspy_owners_low: int | float | None = None
    steamspy_owners_high: int | float | None = None
    selected_game_price_usd: int | float | None = None
    realized_price_fraction: int | float | None = 0.70
    platform_fee_rate: int | float | None = 0.30
    twitch_channel_count: int | float | None = None
    twitch_channel_peer_max: int | float | None = None
    review_count: int | float | None = None
    review_peer_max: int | float | None = None
    comparable_game_count: int | float | None = None
    comparable_game_peer_max: int | float | None = None


@dataclass(frozen=True)
class DeveloperPrediction:
    """Deterministic estimated ranges and peer-relative competition output."""

    estimated_owner_units: tuple[int, int] | None
    scenario_gross_usd: tuple[float, float] | None
    scenario_net_usd: tuple[float, float] | None
    realized_price_fraction: float
    platform_fee_rate: float
    assumptions: tuple[str, ...]
    source_caveat: str
    confidence: str
    competition_index: float | None
    competition_explanation: str


def _finite_nonnegative(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _normalise_assumption(
    value: object,
    default: float,
    label: str,
    notes: list[str],
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        notes.append(f"{label} was invalid and defaulted to {default:.0%}.")
        return default
    if not math.isfinite(number):
        notes.append(f"{label} was non-finite and defaulted to {default:.0%}.")
        return default
    bounded = max(0.0, min(1.0, number))
    if bounded != number:
        notes.append(f"{label} was clamped to {bounded:.0%}.")
    return bounded


def _owner_range(values: DeveloperPredictionInput) -> tuple[int, int] | None:
    low = _finite_nonnegative(values.steamspy_owners_low)
    high = _finite_nonnegative(values.steamspy_owners_high)
    if low is None or high is None:
        return None
    bounds = (int(low), int(high))
    return tuple(sorted(bounds))


def _peer_pressure(value: object, peer_max: object) -> float | None:
    observed = _finite_nonnegative(value)
    maximum = _finite_nonnegative(peer_max)
    if observed is None or maximum is None or maximum <= 0:
        return None
    return max(0.0, min(1.0, observed / maximum))


def _money_range(
    owners: tuple[int, int],
    price: float,
    multiplier: float,
) -> tuple[float, float] | None:
    amounts = tuple(owner_count * price * multiplier for owner_count in owners)
    if not all(math.isfinite(amount) for amount in amounts):
        return None
    return tuple(round(amount, 2) for amount in amounts)


def _competition(values: DeveloperPredictionInput) -> tuple[float | None, str]:
    factors = (
        ("TwitchTracker channel pressure", values.twitch_channel_count, values.twitch_channel_peer_max, 0.50),
        ("comparable-game pressure", values.comparable_game_count, values.comparable_game_peer_max, 0.30),
        ("review pressure", values.review_count, values.review_peer_max, 0.20),
    )
    included: list[tuple[str, float, float]] = []
    excluded: list[str] = []
    for label, value, peer_max, weight in factors:
        pressure = _peer_pressure(value, peer_max)
        if pressure is None:
            excluded.append(label)
        else:
            included.append((label, pressure, weight))

    if not included:
        return None, "Competition index unavailable: no valid peer-relative channel, comparable-game, or review factor was supplied."

    total_weight = sum(weight for _, _, weight in included)
    score = sum(pressure * weight for _, pressure, weight in included) / total_weight * 100
    included_text = ", ".join(label for label, _, _ in included)
    excluded_text = ", ".join(excluded) if excluded else "none"
    explanation = (
        f"Competition index includes {included_text}; excluded factors: {excluded_text}. "
        "Each included factor is observed value divided by its caller-provided peer maximum, "
        "and the 0.50/0.30/0.20 weights are renormalized across included factors."
    )
    return round(max(0.0, min(100.0, score)), 2), explanation


def predict_developer_outcome(values: DeveloperPredictionInput) -> DeveloperPrediction:
    """Calculate explicit ownership, revenue, and competition scenarios."""
    assumption_notes: list[str] = []
    realized_fraction = _normalise_assumption(
        values.realized_price_fraction,
        0.70,
        "Realised-price fraction",
        assumption_notes,
    )
    fee_rate = _normalise_assumption(
        values.platform_fee_rate,
        0.30,
        "Platform-fee rate",
        assumption_notes,
    )

    owners = _owner_range(values)
    price = _finite_nonnegative(values.selected_game_price_usd)
    gross: tuple[float, float] | None = None
    net: tuple[float, float] | None = None
    if owners is not None and price is not None:
        gross = _money_range(owners, price, realized_fraction)
        if gross is not None:
            net = _money_range(gross, 1.0, 1.0 - fee_rate)

    assumptions = [
        "Estimated owner units use the normalized SteamSpy owner range.",
        "Gross scenario = estimated owner units × selected-game USD price × realised-price fraction.",
        "Net scenario = gross scenario × (1 − platform-fee rate).",
        f"Realised-price fraction assumption: {realized_fraction:.1%}.",
        f"Platform-fee rate assumption: {fee_rate:.1%}.",
    ]
    assumptions.extend(assumption_notes)

    caveats = [
        "SteamSpy owner ranges are third-party ownership estimates, not verified units sold.",
        "Gross and net values are explicit scenario estimates, not actual sales or revenue.",
    ]
    if owners is None:
        caveats.append("Owner-unit range is unavailable because both valid SteamSpy bounds are required.")
    if price is None:
        caveats.append("Revenue scenarios are unavailable because the selected-game USD price is missing or invalid.")

    competition_index, competition_explanation = _competition(values)
    if gross is not None:
        confidence = "medium"
    elif owners is not None or competition_index is not None:
        confidence = "limited"
    else:
        confidence = "unknown"
    return DeveloperPrediction(
        estimated_owner_units=owners,
        scenario_gross_usd=gross,
        scenario_net_usd=net,
        realized_price_fraction=realized_fraction,
        platform_fee_rate=fee_rate,
        assumptions=tuple(assumptions),
        source_caveat=" ".join(caveats),
        confidence=confidence,
        competition_index=competition_index,
        competition_explanation=competition_explanation,
    )

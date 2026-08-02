"""Explicit, reusable time-window growth calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Iterable, Mapping


# A baseline must be near the requested interval, rather than merely being
# older than the latest observation. Bounds are inclusive and expressed in
# hours: one-day = 18-30 hours, seven-day = 6-8 days.
WINDOW_TOLERANCES: dict[str, tuple[float, float, float]] = {
    "one-day": (24.0, 18.0, 30.0),
    "seven-day": (168.0, 144.0, 192.0),
}


@dataclass(frozen=True)
class GrowthComparison:
    """A windowed percentage change and the observations that support it."""

    window: str
    target_interval_hours: float
    percentage_change: float | None
    actual_interval_hours: float | None
    baseline_timestamp: str | None
    latest_timestamp: str | None
    available: bool
    reason: str | None = None


@dataclass(frozen=True)
class _ValidObservation:
    timestamp: datetime
    timestamp_text: str
    viewers: float


def _field(row: object, name: str) -> object:
    if isinstance(row, Mapping):
        return row.get(name)
    return getattr(row, name, None)


def _parse_timestamp(value: object) -> tuple[datetime, str] | None:
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return parsed, parsed.isoformat()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed, str(value)


def _valid_observations(observations: Iterable[object], value_field: str, timestamp_field: str) -> list[_ValidObservation]:
    valid: list[_ValidObservation] = []
    for row in observations:
        parsed = _parse_timestamp(_field(row, timestamp_field))
        try:
            viewers = float(_field(row, value_field))
        except (TypeError, ValueError):
            continue
        if parsed is None or not math.isfinite(viewers) or viewers < 0:
            continue
        valid.append(_ValidObservation(parsed[0], parsed[1], viewers))
    return valid


def _window_name(window: str | int) -> str:
    normalized = str(window).strip().casefold().replace("_", "-")
    aliases = {"1": "one-day", "1-day": "one-day", "24h": "one-day", "7": "seven-day", "7-day": "seven-day", "168h": "seven-day"}
    return aliases.get(normalized, normalized)


def _unavailable(window: str, target_hours: float, latest: _ValidObservation | None) -> GrowthComparison:
    return GrowthComparison(
        window=window,
        target_interval_hours=target_hours,
        percentage_change=None,
        actual_interval_hours=None,
        baseline_timestamp=None,
        latest_timestamp=latest.timestamp_text if latest else None,
        available=False,
        reason="insufficient history",
    )


def calculate_window_growth(
    observations: Iterable[object],
    window: str | int = "seven-day",
    *,
    value_field: str = "viewer_count",
    timestamp_field: str = "observed_at",
) -> GrowthComparison:
    """Select the closest valid baseline inside the configured time window.

    Invalid timestamps/viewer values are ignored. The latest valid observation
    must have a non-negative viewer count; the baseline must have a positive
    viewer count so division by zero cannot produce a misleading comparison.
    """

    name = _window_name(window)
    if name not in WINDOW_TOLERANCES:
        raise ValueError(f"Unsupported growth window: {window}")
    target_hours, minimum_hours, maximum_hours = WINDOW_TOLERANCES[name]
    valid = sorted(_valid_observations(observations, value_field, timestamp_field), key=lambda item: item.timestamp)
    if not valid:
        return _unavailable(name, target_hours, None)
    latest = valid[-1]
    candidates = []
    for observation in valid[:-1]:
        interval_hours = (latest.timestamp - observation.timestamp).total_seconds() / 3600.0
        if minimum_hours <= interval_hours <= maximum_hours and observation.viewers > 0:
            candidates.append((abs(interval_hours - target_hours), -observation.timestamp.timestamp(), interval_hours, observation))
    if not candidates:
        return _unavailable(name, target_hours, latest)
    _distance, _recency, interval_hours, baseline = min(candidates)
    percentage_change = (latest.viewers - baseline.viewers) / baseline.viewers
    return GrowthComparison(
        window=name,
        target_interval_hours=target_hours,
        percentage_change=percentage_change,
        actual_interval_hours=interval_hours,
        baseline_timestamp=baseline.timestamp_text,
        latest_timestamp=latest.timestamp_text,
        available=True,
    )

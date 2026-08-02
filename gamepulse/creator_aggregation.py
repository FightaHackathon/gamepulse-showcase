"""Pure aggregation helpers for creator observation history."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping


_OBSERVATION_IDENTITY_FIELDS = (
    "observed_at",
    "stream_id",
    "streamer_id",
    "game_id",
    "game_name",
    "viewer_count",
)


@dataclass(frozen=True)
class CategoryAggregation:
    """Category frequency data and display-oriented history."""

    chronological_categories: tuple[str, ...]
    display_categories: tuple[str, ...]
    primary_category: str | None
    primary_category_share: float | None


def _timestamp_key(value: object) -> datetime:
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


def deduplicate_observations(records: Iterable[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    """Remove exact observation copies while retaining observations over time.

    Observation identity is the tuple of timestamp, stream/creator identity,
    game identity/name, and viewer count. Source, collection, and coverage
    metadata are intentionally excluded so provider and database copies of the
    same observation count once. A different timestamp or stream identity is
    a legitimate observation and is retained.
    """

    result: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for record in records:
        key = tuple(record.get(field) for field in _OBSERVATION_IDENTITY_FIELDS)
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(record))
    return tuple(result)


def aggregate_creator_categories(records: Iterable[Mapping[str, object]]) -> CategoryAggregation:
    """Aggregate valid category observations without losing frequency data."""

    deduplicated = deduplicate_observations(records)
    ordered = tuple(
        record
        for _index, record in sorted(
            enumerate(deduplicated),
            key=lambda item: (_timestamp_key(item[1].get("observed_at")), item[0]),
        )
    )
    chronological = tuple(
        category
        for record in ordered
        if (category := str(record.get("game_name") or "").strip())
    )
    display_categories = tuple(dict.fromkeys(chronological))
    counts = Counter(chronological)
    primary_category = counts.most_common(1)[0][0] if counts else None
    primary_share = counts[primary_category] / len(chronological) if primary_category else None
    return CategoryAggregation(
        chronological_categories=chronological,
        display_categories=display_categories,
        primary_category=primary_category,
        primary_category_share=primary_share,
    )

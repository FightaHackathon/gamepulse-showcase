from __future__ import annotations

import hashlib
import re
from typing import Any

from .source_io import optional_int, parse_bool


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalise_review_row(row: dict[str, str]) -> dict[str, Any] | None:
    app_id = optional_int(row.get("appid"))
    review_text = _clean_text(row.get("review"))
    if app_id is None or not review_text:
        return None
    created_at = optional_int(row.get("timestamp_created"))
    playtime = optional_int(row.get("author_playtime_forever"))
    review_id_source = "|".join(
        [str(app_id), str(created_at or ""), str(playtime or ""), review_text]
    )
    return {
        "review_id": hashlib.sha256(review_id_source.encode("utf-8")).hexdigest(),
        "steam_app_id": app_id,
        "review_text": review_text,
        "word_count": optional_int(row.get("word_count")) or len(review_text.split()),
        "recommended": parse_bool(row.get("voted_up")),
        "helpful_votes": optional_int(row.get("votes_up")) or 0,
        "funny_votes": optional_int(row.get("votes_funny")) or 0,
        "created_at_unix": created_at,
        "author_playtime_minutes": playtime,
        "source_game_name": _clean_text(row.get("name")) or None,
        "source_price": optional_int(row.get("price")),
        "source_release_date": _clean_text(row.get("release_date")) or None,
    }


class ReviewSummaryAccumulator:
    """Maintain per-game review aggregates while rows stream from disk."""

    def __init__(self) -> None:
        self.summaries: dict[int, dict[str, Any]] = {}

    def add(self, row: dict[str, Any]) -> None:
        app_id = int(row["steam_app_id"])
        summary = self.summaries.setdefault(
            app_id,
            {
                "steam_app_id": app_id,
                "review_count": 0,
                "recommended_count": 0,
                "not_recommended_count": 0,
                "helpful_votes_total": 0,
                "funny_votes_total": 0,
                "word_count_total": 0,
                "playtime_total": 0,
                "playtime_observations": 0,
                "latest_review_created_at_unix": None,
            },
        )
        summary["review_count"] += 1
        if row["recommended"] is True:
            summary["recommended_count"] += 1
        elif row["recommended"] is False:
            summary["not_recommended_count"] += 1
        summary["helpful_votes_total"] += int(row["helpful_votes"])
        summary["funny_votes_total"] += int(row["funny_votes"])
        summary["word_count_total"] += int(row["word_count"])
        if row["author_playtime_minutes"] is not None:
            summary["playtime_total"] += int(row["author_playtime_minutes"])
            summary["playtime_observations"] += 1
        timestamp = row["created_at_unix"]
        if timestamp is not None and (
            summary["latest_review_created_at_unix"] is None
            or timestamp > summary["latest_review_created_at_unix"]
        ):
            summary["latest_review_created_at_unix"] = timestamp

    def finalize(self) -> dict[int, dict[str, Any]]:
        for summary in self.summaries.values():
            review_count = summary["review_count"]
            summary["review_score"] = round(
                summary["recommended_count"] / review_count, 6
            )
            summary["average_word_count"] = round(
                summary["word_count_total"] / review_count, 2
            )
            observation_count = summary.pop("playtime_observations")
            playtime_total = summary.pop("playtime_total")
            summary["average_playtime_minutes"] = (
                round(playtime_total / observation_count, 2)
                if observation_count
                else None
            )
            summary.pop("word_count_total")
        return self.summaries


def summarise_reviews(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    accumulator = ReviewSummaryAccumulator()
    for row in rows:
        accumulator.add(row)
    return accumulator.finalize()

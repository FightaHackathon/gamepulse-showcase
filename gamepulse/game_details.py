"""Read-only game detail and review-catalogue queries for the prototype UI."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from gamepulse.catalog import Catalog, GameSummary
from gamepulse.database import connect_read_only
from gamepulse.review_analysis import ReviewAnalysis, analyze_reviews


@dataclass(frozen=True)
class ReviewRecord:
    review_id: str
    review_text: str
    recommended: bool | None
    helpful_votes: int
    funny_votes: int
    created_at_unix: int | None
    author_playtime_minutes: int | None


@dataclass(frozen=True)
class ReviewCatalogue:
    review_count: int
    recommended_count: int
    not_recommended_count: int
    review_score: float | None
    average_playtime_minutes: float | None
    helpful_votes_total: int
    funny_votes_total: int
    reviews: tuple[ReviewRecord, ...]


@dataclass(frozen=True)
class GameDetails:
    game: GameSummary
    review_catalogue: ReviewCatalogue
    analysis: ReviewAnalysis


def _as_int(value, default: int = 0) -> int:
    return default if value is None else int(value)


def _as_float(value) -> float | None:
    return None if value is None else float(value)


def _review_record(row: sqlite3.Row) -> ReviewRecord:
    recommended = row["recommended"]
    return ReviewRecord(
        review_id=str(row["review_id"]),
        review_text=str(row["review_text"]),
        recommended=None if recommended is None else bool(recommended),
        helpful_votes=_as_int(row["helpful_votes"]),
        funny_votes=_as_int(row["funny_votes"]),
        created_at_unix=None if row["created_at_unix"] is None else int(row["created_at_unix"]),
        author_playtime_minutes=None if row["author_playtime_minutes"] is None else int(row["author_playtime_minutes"]),
    )


def get_game_details(database_path: Path, app_id: int, review_limit: int = 20) -> GameDetails:
    """Return catalogue metadata, aggregate review signals, and newest review rows."""
    game = Catalog(database_path).get_game(app_id)
    bounded_limit = max(1, min(int(review_limit), 100))
    connection = connect_read_only(database_path)
    try:
        summary = connection.execute(
            "SELECT review_count, recommended_count, not_recommended_count, review_score, "
            "average_playtime_minutes, helpful_votes_total, funny_votes_total "
            "FROM review_summaries WHERE steam_app_id = ?",
            (int(app_id),),
        ).fetchone()
        rows = connection.execute(
            "SELECT review_id, review_text, recommended, helpful_votes, funny_votes, "
            "created_at_unix, author_playtime_minutes FROM reviews "
            "WHERE steam_app_id = ? ORDER BY created_at_unix DESC, review_id DESC LIMIT ?",
            (int(app_id), bounded_limit),
        ).fetchall()
    finally:
        connection.close()

    review_catalogue = ReviewCatalogue(
        review_count=_as_int(summary["review_count"] if summary else game.total_reviews),
        recommended_count=_as_int(summary["recommended_count"] if summary else None),
        not_recommended_count=_as_int(summary["not_recommended_count"] if summary else None),
        review_score=_as_float(summary["review_score"] if summary else game.review_score),
        average_playtime_minutes=_as_float(summary["average_playtime_minutes"] if summary else None),
        helpful_votes_total=_as_int(summary["helpful_votes_total"] if summary else None),
        funny_votes_total=_as_int(summary["funny_votes_total"] if summary else None),
        reviews=tuple(_review_record(row) for row in rows),
    )
    analysis = analyze_reviews(database_path, int(app_id), limit=max(bounded_limit, 50))
    return GameDetails(game=game, review_catalogue=review_catalogue, analysis=analysis)

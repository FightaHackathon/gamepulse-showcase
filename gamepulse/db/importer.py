from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import GameGenreModel, GameModel, GameTagModel, ReviewSummaryModel, SteamSnapshotModel


@dataclass(frozen=True)
class ImportReport:
    row_counts: dict[str, int]
    skipped_rows: int
    validation_failures: tuple[str, ...]


class ImportRepository(Protocol):
    def upsert_game(self, row: Mapping[str, object]) -> None: ...
    def replace_tags(self, app_id: int, values: tuple[str, ...]) -> None: ...
    def replace_genres(self, app_id: int, values: tuple[str, ...]) -> None: ...
    def upsert_review_summary(self, row: Mapping[str, object]) -> None: ...
    def upsert_market_snapshot(self, row: Mapping[str, object]) -> None: ...
    def commit(self) -> None: ...


def _parse_observed_at(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("missing observed_at")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class SqlAlchemyImportRepository:
    _GAME_FIELDS = (
        "name",
        "release_date",
        "price_usd",
        "discount_pct",
        "required_age",
        "owners_low",
        "owners_high",
        "peak_ccu",
        "positive_reviews",
        "negative_reviews",
        "total_reviews",
        "review_score",
        "recommendations",
        "average_playtime_minutes",
        "median_playtime_minutes",
        "windows",
        "mac",
        "linux",
        "metacritic_score",
        "header_image_url",
        "website_url",
        "short_description",
    )
    _BOOL_FIELDS = {"windows", "mac", "linux"}
    _REVIEW_FIELDS = (
        "review_count",
        "recommended_count",
        "not_recommended_count",
        "review_score",
        "helpful_votes_total",
        "funny_votes_total",
        "average_word_count",
        "average_playtime_minutes",
        "latest_review_created_at_unix",
    )

    def __init__(self, session: Session):
        self.session = session

    def upsert_game(self, row: Mapping[str, object]) -> None:
        app_id = int(row["steam_app_id"])
        model = self.session.get(GameModel, app_id)
        if model is None:
            model = GameModel(steam_app_id=app_id, name=str(row.get("name") or f"Steam App {app_id}"))
            self.session.add(model)
        for field in self._GAME_FIELDS:
            if field not in row:
                continue
            value = row[field]
            if field in self._BOOL_FIELDS and value is not None:
                value = bool(value)
            setattr(model, field, value)

    def _replace_values(self, model, app_id: int, values: tuple[str, ...]) -> None:
        self.session.execute(delete(model).where(model.steam_app_id == app_id))
        for value in sorted({str(item).strip() for item in values if str(item).strip()}, key=str.casefold):
            self.session.add(model(steam_app_id=app_id, value=value))

    def replace_tags(self, app_id: int, values: tuple[str, ...]) -> None:
        self._replace_values(GameTagModel, app_id, values)

    def replace_genres(self, app_id: int, values: tuple[str, ...]) -> None:
        self._replace_values(GameGenreModel, app_id, values)

    def upsert_review_summary(self, row: Mapping[str, object]) -> None:
        app_id = int(row["steam_app_id"])
        model = self.session.get(ReviewSummaryModel, app_id)
        if model is None:
            model = ReviewSummaryModel(steam_app_id=app_id)
            self.session.add(model)
        for field in self._REVIEW_FIELDS:
            if field in row:
                setattr(model, field, row[field])

    def upsert_market_snapshot(self, row: Mapping[str, object]) -> None:
        app_id = int(row["steam_app_id"])
        observed_at = _parse_observed_at(row.get("observed_at"))
        source_name = str(row.get("source_name") or "Prototype SQLite")
        source_mode = str(row.get("source_mode") or "imported_snapshot")
        confidence = str(row.get("confidence") or "medium")
        source_url = str(row["source_url"]) if row.get("source_url") else None
        metrics = {
            "peak_ccu": row.get("peak_ccu"),
            "total_reviews": row.get("total_reviews"),
            "price_usd": row.get("price_usd"),
            "discount_pct": row.get("discount_pct"),
        }
        for metric, value in metrics.items():
            if value is None:
                continue
            existing = self.session.scalars(
                select(SteamSnapshotModel).where(
                    SteamSnapshotModel.steam_app_id == app_id,
                    SteamSnapshotModel.metric == metric,
                    SteamSnapshotModel.observed_at == observed_at,
                    SteamSnapshotModel.source_name == source_name,
                )
            ).first()
            if existing is None:
                existing = SteamSnapshotModel(
                    steam_app_id=app_id,
                    metric=metric,
                    observed_at=observed_at,
                    source_name=source_name,
                    source_mode=source_mode,
                    confidence=confidence,
                    source_url=source_url,
                )
                self.session.add(existing)
            existing.value_numeric = float(value)
            existing.value_text = None
            existing.source_mode = source_mode
            existing.confidence = confidence
            existing.source_url = source_url

    def commit(self) -> None:
        self.session.commit()


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)
    ).fetchone() is not None


def _group_values(connection: sqlite3.Connection, table: str) -> dict[int, tuple[str, ...]]:
    if not _table_exists(connection, table):
        return {}
    grouped: dict[int, list[str]] = {}
    for row in connection.execute(f"SELECT steam_app_id, value FROM {table} ORDER BY steam_app_id, value COLLATE NOCASE"):
        grouped.setdefault(int(row["steam_app_id"]), []).append(str(row["value"]))
    return {app_id: tuple(values) for app_id, values in grouped.items()}


def import_sqlite(sqlite_path: Path, repository: ImportRepository) -> ImportReport:
    row_counts = {"games": 0, "tags": 0, "genres": 0, "review_summaries": 0, "market_snapshots": 0}
    skipped_rows = 0
    failures: list[str] = []
    connection = sqlite3.connect(Path(sqlite_path))
    connection.row_factory = sqlite3.Row
    try:
        tags = _group_values(connection, "game_tags")
        genres = _group_values(connection, "game_genres")
        if not _table_exists(connection, "games"):
            raise ValueError("source SQLite database has no games table")
        for row in connection.execute("SELECT * FROM games ORDER BY steam_app_id"):
            try:
                data = dict(row)
                app_id = int(data["steam_app_id"])
                repository.upsert_game(data)
                repository.replace_tags(app_id, tags.get(app_id, ()))
                repository.replace_genres(app_id, genres.get(app_id, ()))
                row_counts["games"] += 1
                row_counts["tags"] += len(tags.get(app_id, ()))
                row_counts["genres"] += len(genres.get(app_id, ()))
            except Exception as exc:
                skipped_rows += 1
                failures.append(f"game:{dict(row).get('steam_app_id')}: {exc}")

        if _table_exists(connection, "review_summaries"):
            for row in connection.execute("SELECT * FROM review_summaries ORDER BY steam_app_id"):
                try:
                    repository.upsert_review_summary(dict(row))
                    row_counts["review_summaries"] += 1
                except Exception as exc:
                    skipped_rows += 1
                    failures.append(f"review:{dict(row).get('steam_app_id')}: {exc}")

        if _table_exists(connection, "steam_market_snapshots"):
            for row in connection.execute("SELECT * FROM steam_market_snapshots ORDER BY steam_app_id, observed_at"):
                try:
                    repository.upsert_market_snapshot(dict(row))
                    row_counts["market_snapshots"] += 1
                except Exception as exc:
                    skipped_rows += 1
                    failures.append(f"market:{dict(row).get('steam_app_id')}: {exc}")
        repository.commit()
    finally:
        connection.close()
    return ImportReport(row_counts=row_counts, skipped_rows=skipped_rows, validation_failures=tuple(failures))

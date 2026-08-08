"""Import the recovered GamePulse SQLite catalog into the Fusion schema.

The importer is intentionally separate from ``bootstrap_catalog``.  The
bootstrap job is a bounded provider smoke test; this job is the historical
catalog migration and keeps every source row that has a corresponding Fusion
model.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Iterable, Mapping

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from gamepulse.db.models import (
    Base,
    GameGenreModel,
    GameModel,
    GameTagModel,
    ProviderRunModel,
    ReviewModel,
    ReviewSummaryModel,
    SteamSnapshotModel,
    SteamSpySnapshotModel,
    StreamingSnapshotModel,
    TrendScoreModel,
)
from gamepulse.db.session import make_engine


DEFAULT_SQLITE_PATH = Path("data/prototype/gamepulse_prototype.sqlite3")
SOURCE_NAME = "GamePulse prototype SQLite"
SOURCE_MODE = "historical_import"


@dataclass(frozen=True)
class FullImportReport:
    status: str
    source_path: str
    source_size_bytes: int
    row_counts: dict[str, int]
    skipped_rows: int
    validation_failures: tuple[str, ...]
    import_seconds: float
    trend_observed_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _as_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"", "null", "none"}:
            return None
        if normalized in {"false", "0", "no"}:
            return False
        if normalized in {"true", "1", "yes"}:
            return True
    return bool(value)


def _parse_timestamp(value: object) -> datetime | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _row_dict(row: sqlite3.Row) -> dict[str, object]:
    return {key: row[key] for key in row.keys()}


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table,),
        ).fetchone()
        is not None
    )


def _chunks(rows: Iterable[dict[str, object]], size: int) -> Iterable[list[dict[str, object]]]:
    batch: list[dict[str, object]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _insert_for_dialect(session: Session):
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return postgres_insert
    if dialect == "sqlite":
        return sqlite_insert
    raise ValueError(f"unsupported import target dialect: {dialect}")


def _upsert_batch(
    session: Session,
    model: type[Base],
    rows: list[dict[str, object]],
    *,
    conflict_columns: tuple[str, ...],
    update_columns: tuple[str, ...],
) -> None:
    if not rows:
        return
    table = model.__table__
    # Use driver-level executemany instead of a multi-values statement.  This
    # keeps the importer below SQLite's host-parameter limit while retaining
    # the same batched behavior on Postgres.
    statement = _insert_for_dialect(session)(table)
    conflict = [table.c[name] for name in conflict_columns]
    if update_columns:
        excluded = statement.excluded
        statement = statement.on_conflict_do_update(
            index_elements=conflict,
            set_={name: getattr(excluded, name) for name in update_columns},
        )
    else:
        statement = statement.on_conflict_do_nothing(index_elements=conflict)
    session.execute(statement, rows)
    session.commit()


def _game_row(source: Mapping[str, object]) -> dict[str, object] | None:
    app_id = _as_int(source.get("steam_app_id"))
    name = str(source.get("name") or "").strip()
    if app_id is None or app_id <= 0 or not name:
        return None
    integer_fields = {
        "required_age",
        "owners_low",
        "owners_high",
        "peak_ccu",
        "positive_reviews",
        "negative_reviews",
        "total_reviews",
        "recommendations",
    }
    float_fields = {
        "price_usd",
        "discount_pct",
        "review_score",
        "average_playtime_minutes",
        "median_playtime_minutes",
        "metacritic_score",
    }
    bool_fields = {"windows", "mac", "linux"}
    fields = {"steam_app_id": app_id, "name": name}
    for field in (
        "release_date",
        "header_image_url",
        "website_url",
        "short_description",
    ):
        fields[field] = str(source[field]).strip() if source.get(field) is not None and str(source[field]).strip() else None
    for field in integer_fields:
        fields[field] = _as_int(source.get(field))
    for field in float_fields:
        fields[field] = _as_float(source.get(field))
    for field in bool_fields:
        fields[field] = _as_bool(source.get(field))
    return fields


def _review_summary_row(source: Mapping[str, object], game_ids: set[int]) -> dict[str, object] | None:
    app_id = _as_int(source.get("steam_app_id"))
    if app_id is None or app_id not in game_ids:
        return None
    return {
        "steam_app_id": app_id,
        "review_count": _as_int(source.get("review_count")) or 0,
        "recommended_count": _as_int(source.get("recommended_count")) or 0,
        "not_recommended_count": _as_int(source.get("not_recommended_count")) or 0,
        "review_score": _as_float(source.get("review_score")),
        "helpful_votes_total": _as_int(source.get("helpful_votes_total")),
        "funny_votes_total": _as_int(source.get("funny_votes_total")),
        "average_word_count": _as_float(source.get("average_word_count")),
        "average_playtime_minutes": _as_float(source.get("average_playtime_minutes")),
        "latest_review_created_at_unix": _as_int(source.get("latest_review_created_at_unix")),
    }


def _review_row(source: Mapping[str, object], game_ids: set[int]) -> dict[str, object] | None:
    app_id = _as_int(source.get("steam_app_id"))
    review_id = str(source.get("review_id") or "").strip()
    if app_id is None or app_id not in game_ids or not review_id:
        return None
    return {
        "review_id": review_id,
        "steam_app_id": app_id,
        "review_text": str(source.get("review_text") or ""),
        "word_count": _as_int(source.get("word_count")),
        "recommended": _as_bool(source.get("recommended")),
        "helpful_votes": _as_int(source.get("helpful_votes")),
        "funny_votes": _as_int(source.get("funny_votes")),
        "created_at_unix": _as_int(source.get("created_at_unix")),
        "author_playtime_minutes": _as_int(source.get("author_playtime_minutes")),
        "source_game_name": str(source.get("source_game_name") or "").strip() or None,
        "source_price": _as_float(source.get("source_price")),
        "source_release_date": str(source.get("source_release_date") or "").strip() or None,
        "source_name": SOURCE_NAME,
        "source_mode": SOURCE_MODE,
        "source_url": None,
    }


def _market_rows(source: Mapping[str, object], game_ids: set[int]) -> tuple[list[dict[str, object]], dict[str, object] | None, datetime | None]:
    app_id = _as_int(source.get("steam_app_id"))
    observed_at = _parse_timestamp(source.get("observed_at"))
    if app_id is None or app_id not in game_ids or observed_at is None:
        return [], None, observed_at
    source_name = str(source.get("source_name") or SOURCE_NAME)
    source_mode = str(source.get("source_mode") or SOURCE_MODE)
    confidence = str(source.get("confidence") or "medium")
    source_url = str(source.get("source_url")) if source.get("source_url") else None
    metric_name = "current_players" if str(source.get("player_metric") or "").casefold() == "current" else "peak_ccu"
    metrics: list[dict[str, object]] = []
    for metric, value in (
        (metric_name, _as_int(source.get("peak_ccu"))),
        ("total_reviews", _as_int(source.get("total_reviews"))),
        ("price_usd", _as_float(source.get("price_usd"))),
        ("discount_pct", _as_float(source.get("discount_pct"))),
    ):
        if value is None:
            continue
        metrics.append(
            {
                "steam_app_id": app_id,
                "metric": metric,
                "value_numeric": float(value),
                "value_text": None,
                "source_name": source_name,
                "source_mode": source_mode,
                "observed_at": observed_at,
                "confidence": confidence,
                "source_url": source_url,
            }
        )
    owners_low = _as_int(source.get("owners_low"))
    owners_high = _as_int(source.get("owners_high"))
    steamspy = None
    if owners_low is not None or owners_high is not None:
        steamspy = {
            "steam_app_id": app_id,
            "owners_low": owners_low,
            "owners_high": owners_high,
            "source_name": source_name,
            "source_mode": "public_estimate",
            "observed_at": observed_at,
            "confidence": confidence,
            "source_url": source_url,
        }
    return metrics, steamspy, observed_at


def _streaming_rows(source: Mapping[str, object], game_ids: set[int]) -> tuple[list[dict[str, object]], datetime | None]:
    game_id = str(source.get("game_id") or "").strip() or None
    app_id = _as_int(game_id)
    if app_id not in game_ids:
        return [], _parse_timestamp(source.get("observed_at"))
    observed_at = _parse_timestamp(source.get("observed_at"))
    if observed_at is None:
        return [], None
    source_name = str(source.get("source_name") or "TwitchTracker")
    source_mode = str(source.get("source_mode") or "historical_import")
    rows: list[dict[str, object]] = []
    for metric, value in (
        ("average_viewers_30d", _as_float(source.get("viewer_count"))),
        ("average_channels_30d", _as_float(source.get("channel_count"))),
    ):
        if value is None:
            continue
        rows.append(
            {
                "steam_app_id": app_id,
                "external_game_id": game_id,
                "game_name": str(source.get("game_name") or "").strip() or None,
                "metric": metric,
                "value_numeric": value,
                "value_text": None,
                "source_name": source_name,
                "source_mode": source_mode,
                "observed_at": observed_at,
                "confidence": "medium",
                "source_url": None,
            }
        )
    return rows, observed_at


def _bounded_score(value: float, denominator: float) -> float:
    import math

    if value <= 0:
        return 0.0
    return round(max(0.0, min(100.0, 100.0 * math.log1p(value) / math.log1p(denominator))), 4)


def _weighted_score(parts: dict[str, tuple[float | None, float]]) -> tuple[float, bool]:
    available = [(value, weight) for value, weight in parts.values() if value is not None]
    if not available:
        return 0.0, False
    total_weight = sum(weight for _, weight in available)
    return round(sum(float(value) * weight for value, weight in available) / total_weight, 4), True


def _review_percent(value: object) -> float | None:
    score = _as_float(value)
    if score is None:
        return None
    return max(0.0, min(100.0, score * 100.0 if score <= 1.0 else score))


def _import_trends(session: Session, observed_at: datetime, batch_size: int) -> int:
    steam_history: dict[int, dict[str, list[tuple[datetime, float]]]] = {}
    for app_id, metric, observed, value in session.execute(
        select(
            SteamSnapshotModel.steam_app_id,
            SteamSnapshotModel.metric,
            SteamSnapshotModel.observed_at,
            SteamSnapshotModel.value_numeric,
        ).where(SteamSnapshotModel.observed_at <= observed_at)
    ).all():
        if value is not None and metric in {"current_players", "peak_ccu"}:
            steam_history.setdefault(int(app_id), {}).setdefault(str(metric), []).append((observed, float(value)))

    streaming_values: dict[int, dict[str, float]] = {}
    for app_id, metric, value in session.execute(
        select(StreamingSnapshotModel.steam_app_id, StreamingSnapshotModel.metric, StreamingSnapshotModel.value_numeric).where(
            StreamingSnapshotModel.steam_app_id.is_not(None),
            StreamingSnapshotModel.observed_at <= observed_at,
        )
    ).all():
        if app_id is not None and value is not None:
            streaming_values.setdefault(int(app_id), {})[str(metric)] = float(value)

    review_summaries = {
        int(app_id): (review_score, playtime)
        for app_id, review_score, playtime in session.execute(
            select(
                ReviewSummaryModel.steam_app_id,
                ReviewSummaryModel.review_score,
                ReviewSummaryModel.average_playtime_minutes,
            )
        ).all()
    }
    max_review_time = session.scalar(select(func.max(ReviewModel.created_at_unix)))
    review_cutoff = int(max_review_time) - 90 * 24 * 60 * 60 if max_review_time is not None else None
    review_velocity: dict[int, int] = {}
    if review_cutoff is not None:
        review_velocity = {
            int(app_id): int(count)
            for app_id, count in session.execute(
                select(ReviewModel.steam_app_id, func.count(ReviewModel.review_id))
                .where(ReviewModel.created_at_unix >= review_cutoff)
                .group_by(ReviewModel.steam_app_id)
            ).all()
        }

    game_rows = session.execute(
        select(GameModel.steam_app_id, GameModel.name, GameModel.peak_ccu, GameModel.total_reviews, GameModel.review_score, GameModel.average_playtime_minutes)
    ).all()
    game_totals = {int(app_id): int(total_reviews or 0) for app_id, _, _, total_reviews, _, _ in game_rows}
    genres_by_game: dict[int, list[str]] = {}
    genre_stats: dict[str, list[int]] = {}
    for app_id, value in session.execute(select(GameGenreModel.steam_app_id, GameGenreModel.value)).all():
        if int(app_id) not in game_totals:
            continue
        genre = str(value)
        genres_by_game.setdefault(int(app_id), []).append(genre)
        stat = genre_stats.setdefault(genre, [0, 0])
        stat[0] += 1
        stat[1] += game_totals[int(app_id)]
    genre_signals = {
        genre: {
            "demand": _bounded_score(total_reviews / max(game_count, 1), 1_000_000),
            "competition": _bounded_score(game_count, 1_000),
        }
        for genre, (game_count, total_reviews) in genre_stats.items()
    }

    trend_rows: list[dict[str, object]] = []
    for app_id, name, peak_ccu, total_reviews, review_score, game_playtime in game_rows:
        app_id = int(app_id)
        history = steam_history.get(app_id, {})
        current_history = sorted(history.get("current_players", []))
        peak_history = sorted(history.get("peak_ccu", []))
        current_players = current_history[-1][1] if current_history else None
        peak = peak_history[-1][1] if peak_history else _as_float(peak_ccu)
        growth_pct = None
        growth_history = current_history or peak_history
        if len(growth_history) >= 2 and growth_history[0][1] > 0:
            growth_pct = (growth_history[-1][1] - growth_history[0][1]) / growth_history[0][1] * 100.0
        growth_score = max(0.0, min(100.0, 50.0 + float(growth_pct))) if growth_pct is not None else None
        summary_review, summary_playtime = review_summaries.get(app_id, (None, None))
        review = _review_percent(summary_review if summary_review is not None else review_score)
        velocity_count = review_velocity.get(app_id)
        velocity = _bounded_score(velocity_count, 10_000) if velocity_count is not None else None
        playtime = _as_float(summary_playtime if summary_playtime is not None else game_playtime)
        playtime_signal = _bounded_score(playtime, 50_000) if playtime is not None else None
        activity_signal = _bounded_score(current_players if current_players is not None else peak, 1_000_000) if (current_players is not None or peak is not None) else None
        player_score, player_available = _weighted_score(
            {
                "activity": (activity_signal, 0.30),
                "growth": (growth_score, 0.20),
                "review": (review, 0.20),
                "velocity": (velocity, 0.15),
                "playtime": (playtime_signal, 0.15),
            }
        )
        game_genres = genres_by_game.get(app_id, [])
        genre_demand = max((genre_signals[genre]["demand"] for genre in game_genres if genre in genre_signals), default=None)
        genre_competition = max((genre_signals[genre]["competition"] for genre in game_genres if genre in genre_signals), default=None)
        market_demand = _bounded_score(float(total_reviews), 1_000_000) if total_reviews is not None else None
        opportunity_gap = genre_demand * (100.0 - genre_competition) / 100.0 if genre_demand is not None and genre_competition is not None else None
        developer_score, developer_available = _weighted_score(
            {
                "market_demand": (market_demand, 0.25),
                "genre_demand": (genre_demand, 0.20),
                "review_sentiment": (review, 0.20),
                "opportunity_gap": (opportunity_gap, 0.20),
                "review_velocity": (velocity, 0.15),
            }
        )
        trend_rows.extend(
            [
                {
                    "steam_app_id": app_id,
                    "audience": "player",
                    "score": player_score,
                    "components": {
                        "current_players": current_players,
                        "player_growth_pct": growth_pct,
                        "peak_ccu": peak,
                        "review_score": review,
                        "review_velocity": velocity_count,
                        "playtime_minutes": playtime,
                        "activity_available": activity_signal is not None,
                        "growth_available": growth_pct is not None,
                        "review_velocity_available": velocity_count is not None,
                        "playtime_available": playtime is not None,
                        "signals_available": player_available,
                    },
                    "observed_at": observed_at,
                    "source_name": "GamePulse Full Catalog Import",
                    "source_mode": "derived_multi_signal",
                    "confidence": "medium" if player_available else "low",
                },
                {
                    "steam_app_id": app_id,
                    "audience": "developer",
                    "score": developer_score,
                    "components": {
                        "market_demand": market_demand,
                        "genre_demand": genre_demand,
                        "genre_competition": genre_competition,
                        "review_sentiment": review,
                        "opportunity_gap": opportunity_gap,
                        "review_velocity": velocity,
                        "genre_demand_available": genre_demand is not None,
                        "opportunity_gap_available": opportunity_gap is not None,
                        "signals_available": developer_available,
                    },
                    "observed_at": observed_at,
                    "source_name": "GamePulse Full Catalog Import",
                    "source_mode": "derived_multi_signal",
                    "confidence": "medium" if developer_available else "low",
                },
            ]
        )
        stream = streaming_values.get(app_id)
        if stream:
            demand_signals = [
                _bounded_score(stream["average_viewers_30d"], 100_000) if stream.get("average_viewers_30d") is not None else None,
                _bounded_score(stream["hours_watched_30d"], 100_000) if stream.get("hours_watched_30d") is not None else None,
            ]
            demand = max((value for value in demand_signals if value is not None), default=None)
            competition = _bounded_score(stream.get("average_channels_30d"), 10_000) if stream.get("average_channels_30d") is not None else None
            stream_gap = demand * (100.0 - competition) / 100.0 if competition is not None else None
            streamer_score, streamer_available = _weighted_score(
                {
                    "demand": (demand, 0.40),
                    "competition_inverse": (100.0 - competition if competition is not None else None, 0.25),
                    "opportunity_gap": (stream_gap, 0.35),
                }
            )
            trend_rows.append(
                {
                    "steam_app_id": app_id,
                    "audience": "streamer",
                    "score": streamer_score,
                    "components": {
                        "streaming_available": True,
                        "demand": demand,
                        "competition": competition,
                        "category_saturation": competition,
                        "opportunity_gap": stream_gap,
                        "hours_watched_30d": stream.get("hours_watched_30d"),
                        "average_viewers_30d": stream.get("average_viewers_30d"),
                        "average_channels_30d": stream.get("average_channels_30d"),
                        "signals_available": streamer_available,
                    },
                    "observed_at": observed_at,
                    "source_name": "GamePulse Full Catalog Import",
                    "source_mode": "derived_multi_signal",
                    "confidence": "medium",
                }
            )

        if len(trend_rows) >= batch_size:
            _upsert_batch(
                session,
                TrendScoreModel,
                trend_rows,
                conflict_columns=("steam_app_id", "audience", "observed_at"),
                update_columns=("score", "components", "source_name", "source_mode", "confidence"),
            )
            trend_rows = []
    if trend_rows:
        _upsert_batch(
            session,
            TrendScoreModel,
            trend_rows,
            conflict_columns=("steam_app_id", "audience", "observed_at"),
            update_columns=("score", "components", "source_name", "source_mode", "confidence"),
        )
    return len(
        session.execute(
            select(TrendScoreModel.id).where(
                TrendScoreModel.observed_at == observed_at,
                TrendScoreModel.source_name == "GamePulse Full Catalog Import",
            )
        ).all()
    )


def _record_provider_run(
    session: Session,
    *,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    metrics_written: int,
    error_text: str | None = None,
) -> None:
    session.add(
        ProviderRunModel(
            provider_name="Full SQLite Catalog Import",
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            metrics_written=metrics_written,
            error_text=error_text,
        )
    )
    session.commit()


def run_full_import(
    sqlite_path: Path | str,
    database_url: str,
    *,
    batch_size: int = 2000,
    observed_at: datetime | str | None = None,
) -> FullImportReport:
    source_path = Path(sqlite_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite source does not exist: {source_path}")
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    source_size = source_path.stat().st_size
    started_clock = time.monotonic()
    started_at = datetime.now(timezone.utc)
    counts = {
        "games": 0,
        "game_tags": 0,
        "game_genres": 0,
        "review_summaries": 0,
        "reviews": 0,
        "steam_snapshots": 0,
        "streaming_snapshots": 0,
        "steamspy_snapshots": 0,
        "trend_scores": 0,
        "provider_runs": 0,
    }
    skipped = 0
    failures: list[str] = []
    game_ids: set[int] = set()
    source_observed: list[datetime] = []
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    connection = sqlite3.connect(source_path)
    connection.row_factory = sqlite3.Row
    try:
        with Session(engine, expire_on_commit=False) as session:
            if not _table_exists(connection, "games"):
                raise ValueError("source SQLite database has no games table")

            for batch in _chunks((_game_row(_row_dict(row)) for row in connection.execute("SELECT * FROM games ORDER BY steam_app_id")), batch_size):
                valid = [row for row in batch if row is not None]
                skipped += len(batch) - len(valid)
                game_ids.update(int(row["steam_app_id"]) for row in valid)
                _upsert_batch(
                    session,
                    GameModel,
                    valid,
                    conflict_columns=("steam_app_id",),
                    update_columns=tuple(field for field in valid[0] if field != "steam_app_id") if valid else (),
                )
                counts["games"] += len(valid)

            for table, model, columns in (
                ("game_tags", GameTagModel, ("steam_app_id", "value")),
                ("game_genres", GameGenreModel, ("steam_app_id", "value")),
            ):
                if not _table_exists(connection, table):
                    continue
                rows: list[dict[str, object]] = []
                accepted = 0
                for raw in connection.execute(f"SELECT steam_app_id, value FROM {table} ORDER BY steam_app_id, value COLLATE NOCASE"):
                    source = _row_dict(raw)
                    app_id = _as_int(source.get("steam_app_id"))
                    value = str(source.get("value") or "").strip()
                    if app_id is None or app_id not in game_ids or not value:
                        skipped += 1
                        continue
                    rows.append({"steam_app_id": app_id, "value": value})
                    accepted += 1
                    if len(rows) >= batch_size:
                        _upsert_batch(session, model, rows, conflict_columns=columns, update_columns=())
                        rows = []
                if rows:
                    _upsert_batch(session, model, rows, conflict_columns=columns, update_columns=())
                counts["game_tags" if table == "game_tags" else "game_genres"] = accepted

            if _table_exists(connection, "review_summaries"):
                for batch in _chunks(
                    (_review_summary_row(_row_dict(row), game_ids) for row in connection.execute("SELECT * FROM review_summaries ORDER BY steam_app_id")),
                    batch_size,
                ):
                    valid = [row for row in batch if row is not None]
                    skipped += len(batch) - len(valid)
                    _upsert_batch(
                        session,
                        ReviewSummaryModel,
                        valid,
                        conflict_columns=("steam_app_id",),
                        update_columns=(
                            "review_count",
                            "recommended_count",
                            "not_recommended_count",
                            "review_score",
                            "helpful_votes_total",
                            "funny_votes_total",
                            "average_word_count",
                            "average_playtime_minutes",
                            "latest_review_created_at_unix",
                        ),
                    )
                    counts["review_summaries"] += len(valid)

            if _table_exists(connection, "reviews"):
                for batch in _chunks(
                    (_review_row(_row_dict(row), game_ids) for row in connection.execute("SELECT * FROM reviews ORDER BY steam_app_id, review_id")),
                    batch_size,
                ):
                    valid = [row for row in batch if row is not None]
                    skipped += len(batch) - len(valid)
                    _upsert_batch(
                        session,
                        ReviewModel,
                        valid,
                        conflict_columns=("review_id",),
                        update_columns=tuple(field for field in valid[0] if field != "review_id") if valid else (),
                    )
                    counts["reviews"] += len(valid)

            if _table_exists(connection, "steam_market_snapshots"):
                market_metrics: list[dict[str, object]] = []
                steamspy_rows: list[dict[str, object]] = []
                for raw in connection.execute("SELECT * FROM steam_market_snapshots ORDER BY steam_app_id, observed_at"):
                    metrics, steamspy, source_time = _market_rows(_row_dict(raw), game_ids)
                    if source_time is not None:
                        source_observed.append(source_time)
                    if not metrics and steamspy is None:
                        skipped += 1
                        continue
                    market_metrics.extend(metrics)
                    if steamspy is not None:
                        steamspy_rows.append(steamspy)
                    if len(market_metrics) >= batch_size:
                        _upsert_batch(
                            session,
                            SteamSnapshotModel,
                            market_metrics,
                            conflict_columns=("steam_app_id", "metric", "observed_at", "source_name"),
                            update_columns=("value_numeric", "value_text", "source_mode", "confidence", "source_url"),
                        )
                        counts["steam_snapshots"] += len(market_metrics)
                        market_metrics = []
                    if len(steamspy_rows) >= batch_size:
                        _upsert_batch(
                            session,
                            SteamSpySnapshotModel,
                            steamspy_rows,
                            conflict_columns=("steam_app_id", "observed_at", "source_name"),
                            update_columns=("owners_low", "owners_high", "source_mode", "confidence", "source_url"),
                        )
                        counts["steamspy_snapshots"] += len(steamspy_rows)
                        steamspy_rows = []
                if market_metrics:
                    _upsert_batch(
                        session,
                        SteamSnapshotModel,
                        market_metrics,
                        conflict_columns=("steam_app_id", "metric", "observed_at", "source_name"),
                        update_columns=("value_numeric", "value_text", "source_mode", "confidence", "source_url"),
                    )
                    counts["steam_snapshots"] += len(market_metrics)
                if steamspy_rows:
                    _upsert_batch(
                        session,
                        SteamSpySnapshotModel,
                        steamspy_rows,
                        conflict_columns=("steam_app_id", "observed_at", "source_name"),
                        update_columns=("owners_low", "owners_high", "source_mode", "confidence", "source_url"),
                    )
                    counts["steamspy_snapshots"] += len(steamspy_rows)

            if _table_exists(connection, "twitch_game_snapshots"):
                stream_rows: list[dict[str, object]] = []
                for raw in connection.execute("SELECT * FROM twitch_game_snapshots ORDER BY observed_at, game_id"):
                    rows, source_time = _streaming_rows(_row_dict(raw), game_ids)
                    if source_time is not None:
                        source_observed.append(source_time)
                    stream_rows.extend(rows)
                    if len(stream_rows) >= batch_size:
                        _upsert_batch(
                            session,
                            StreamingSnapshotModel,
                            stream_rows,
                            conflict_columns=("steam_app_id", "metric", "observed_at", "source_name"),
                            update_columns=("external_game_id", "game_name", "value_numeric", "value_text", "source_mode", "confidence", "source_url"),
                        )
                        counts["streaming_snapshots"] += len(stream_rows)
                        stream_rows = []
                if stream_rows:
                    _upsert_batch(
                        session,
                        StreamingSnapshotModel,
                        stream_rows,
                        conflict_columns=("steam_app_id", "metric", "observed_at", "source_name"),
                        update_columns=("external_game_id", "game_name", "value_numeric", "value_text", "source_mode", "confidence", "source_url"),
                    )
                    counts["streaming_snapshots"] += len(stream_rows)

            trend_time = _parse_timestamp(observed_at)
            if trend_time is None:
                trend_time = max(source_observed, default=datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc))
            counts["trend_scores"] = _import_trends(session, trend_time, batch_size)
            _record_provider_run(
                session,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                status="partial" if failures or skipped else "success",
                metrics_written=sum(value for key, value in counts.items() if key not in {"provider_runs", "trend_scores"}) + counts["trend_scores"],
                error_text="; ".join(failures[:20]) if failures else None,
            )
            counts["provider_runs"] = 1
    except Exception as exc:
        failures.append(str(exc)[:500])
        try:
            with Session(engine) as failure_session:
                _record_provider_run(
                    failure_session,
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                    status="failure",
                    metrics_written=0,
                    error_text=str(exc)[:500],
                )
                counts["provider_runs"] = 1
        except Exception:
            pass
        raise
    finally:
        connection.close()
        engine.dispose()

    return FullImportReport(
        status="partial_success" if failures or skipped else "success",
        source_path=str(source_path),
        source_size_bytes=source_size,
        row_counts=counts,
        skipped_rows=skipped,
        validation_failures=tuple(failures[:20]),
        import_seconds=round(time.monotonic() - started_clock, 3),
        trend_observed_at=(trend_time or started_at).isoformat(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restore the full recovered GamePulse SQLite catalog into Fusion Postgres.")
    parser.add_argument("--sqlite", default=str(DEFAULT_SQLITE_PATH), help="Recovered SQLite source path.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"), help="Target SQLAlchemy DATABASE_URL (or DATABASE_URL environment variable).")
    parser.add_argument("--batch-size", type=int, default=2000, help="Rows per database upsert batch.")
    parser.add_argument("--observed-at", help="Stable ISO-8601 timestamp for derived trend scores.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.database_url:
            raise ValueError("DATABASE_URL is required")
        report = run_full_import(
            args.sqlite,
            args.database_url,
            batch_size=args.batch_size,
            observed_at=args.observed_at,
        )
        print(json.dumps(report.to_dict(), sort_keys=True))
        return 0 if report.status in {"success", "partial_success"} else 1
    except Exception as exc:
        print(json.dumps({"status": "failure", "error": str(exc)[:500]}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

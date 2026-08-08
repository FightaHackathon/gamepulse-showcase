"""Read-only, explainable market intelligence derived from the GamePulse DB.

The database does the aggregation and ranking.  Python only hydrates the
bounded result set requested by the caller, which keeps this slice usable with
the full prepared catalogue as well as small or sparse fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sqlite3
from typing import Iterable

from gamepulse.database import connect_read_only


_WINDOW_SECONDS = 30 * 24 * 60 * 60
_MAX_LIMIT = 100


@dataclass(frozen=True)
class TrendResult:
    steam_app_id: int
    name: str
    score: int
    factors: dict[str, float]
    review_count: int
    recent_reviews: int
    prior_reviews: int
    tags: tuple[str, ...]
    genres: tuple[str, ...]
    comparable_count: int
    explanation: tuple[str, ...]

    @property
    def opportunity_score(self) -> int:
        return self.score

    @property
    def reasons(self) -> tuple[str, ...]:
        return self.explanation

    @property
    def demand(self) -> float:
        return self.factors["demand"]

    @property
    def momentum(self) -> float:
        return self.factors["momentum"]

    @property
    def competition(self) -> float:
        return self.factors["competition"]

    @property
    def saturation(self) -> float:
        return self.factors["saturation"]


@dataclass(frozen=True)
class MarketOpportunity:
    dimension: str
    value: str
    score: int
    factors: dict[str, float]
    matched_games: int
    total_games: int
    recent_reviews: int
    prior_reviews: int
    sample_games: tuple[str, ...]
    explanation: tuple[str, ...]

    @property
    def opportunity_score(self) -> int:
        return self.score

    @property
    def reasons(self) -> tuple[str, ...]:
        return self.explanation

    @property
    def demand(self) -> float:
        return self.factors["demand"]

    @property
    def momentum(self) -> float:
        return self.factors["momentum"]

    @property
    def competition(self) -> float:
        return self.factors["competition"]

    @property
    def saturation(self) -> float:
        return self.factors["saturation"]


@dataclass(frozen=True)
class ComparableGame:
    steam_app_id: int
    name: str
    overlap_score: int
    shared_tags: tuple[str, ...]
    shared_genres: tuple[str, ...]
    review_count: int
    review_score: float | None
    price_usd: float | None
    explanation: tuple[str, ...]

    @property
    def overlap(self) -> int:
        return self.overlap_score


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 3)


def _limit(value: int) -> int:
    try:
        return max(0, min(int(value), _MAX_LIMIT))
    except (TypeError, ValueError):
        return 20


def _fold(value: object) -> str:
    return str(value or "").strip().casefold()


def _integer(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _mean(values: Iterable[float]) -> float:
    values = tuple(values)
    return sum(values) / len(values) if values else 0.0


def _score(factors: dict[str, float]) -> int:
    value = (
        factors["demand"] * 0.35
        + factors["momentum"] * 0.25
        + (1.0 - factors["competition"]) * 0.20
        + (1.0 - factors["saturation"]) * 0.20
    )
    return max(0, min(100, round(value * 100)))


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    except sqlite3.DatabaseError:
        return set()


class DeveloperIntelligence:
    """Bounded, read-only queries for Developer Mode."""

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

    def _open(self) -> sqlite3.Connection | None:
        try:
            return connect_read_only(self.database_path)
        except (OSError, sqlite3.DatabaseError):
            return None

    @staticmethod
    def _dimensions(
        connection: sqlite3.Connection,
        table: str,
        app_ids: tuple[int, ...],
    ) -> dict[int, tuple[str, ...]]:
        if not app_ids or not _table_exists(connection, table):
            return {}
        placeholders = ",".join("?" for _ in app_ids)
        try:
            rows = connection.execute(
                f"SELECT steam_app_id, value FROM {table} "
                f"WHERE steam_app_id IN ({placeholders}) AND value IS NOT NULL AND TRIM(value) <> '' "
                "ORDER BY steam_app_id, value COLLATE NOCASE",
                app_ids,
            ).fetchall()
        except sqlite3.DatabaseError:
            return {}
        values: dict[int, list[str]] = {}
        seen: dict[int, set[str]] = {}
        for row in rows:
            app_id = _integer(row["steam_app_id"])
            value = str(row["value"]).strip()
            folded = _fold(value)
            if value and folded not in seen.setdefault(app_id, set()):
                seen[app_id].add(folded)
                values.setdefault(app_id, []).append(value)
        return {app_id: tuple(items) for app_id, items in values.items()}

    @staticmethod
    def _base_sql(
        connection: sqlite3.Connection,
        *,
        include_dimensions: bool,
    ) -> tuple[str, set[str]]:
        """Return CTEs for metrics; aggregation stays inside SQLite."""
        game_columns = _columns(connection, "games")
        optional = {
            "market": _table_exists(connection, "steam_market_snapshots"),
            "summaries": _table_exists(connection, "review_summaries"),
            "reviews": _table_exists(connection, "reviews"),
            "tags": _table_exists(connection, "game_tags"),
            "genres": _table_exists(connection, "game_genres"),
        }
        owner = "g.owners_high" if "owners_high" in game_columns else "NULL"
        peak = "g.peak_ccu" if "peak_ccu" in game_columns else "NULL"
        reviews = "g.total_reviews" if "total_reviews" in game_columns else "NULL"
        review_score = "g.review_score" if "review_score" in game_columns else "NULL"
        price = "g.price_usd" if "price_usd" in game_columns else "NULL"
        latest_market = ""
        market_join = ""
        if optional["market"]:
            latest_market = """
            latest_market AS (
                SELECT m.steam_app_id, m.observed_at, m.owners_high, m.peak_ccu, m.total_reviews
                FROM steam_market_snapshots m
                WHERE m.observed_at = (
                    SELECT MAX(m2.observed_at) FROM steam_market_snapshots m2
                    WHERE m2.steam_app_id = m.steam_app_id
                )
            ),
            """
            market_join = "LEFT JOIN latest_market lm ON lm.steam_app_id = g.steam_app_id"
            owner = "COALESCE(lm.owners_high, g.owners_high)" if "owners_high" in game_columns else "lm.owners_high"
            peak = "COALESCE(lm.peak_ccu, g.peak_ccu)" if "peak_ccu" in game_columns else "lm.peak_ccu"
            reviews = "COALESCE(lm.total_reviews, g.total_reviews)" if "total_reviews" in game_columns else "lm.total_reviews"
        summary_join = ""
        summary_count = "NULL"
        if optional["summaries"]:
            summary_join = "LEFT JOIN review_summaries rs ON rs.steam_app_id = g.steam_app_id"
            summary_count = "rs.review_count"
        reviews = f"COALESCE({reviews}, {summary_count}, 0)"
        review_cte = ""
        review_join = ""
        if optional["reviews"]:
            review_cte = f"""
            review_latest AS (
                SELECT steam_app_id, MAX(created_at_unix) AS latest_at
                FROM reviews WHERE created_at_unix IS NOT NULL GROUP BY steam_app_id
            ),
            review_windows AS (
                SELECT r.steam_app_id,
                       SUM(CASE WHEN r.created_at_unix > l.latest_at - {_WINDOW_SECONDS} THEN 1 ELSE 0 END) AS recent_reviews,
                       SUM(CASE WHEN r.created_at_unix <= l.latest_at - {_WINDOW_SECONDS}
                                AND r.created_at_unix > l.latest_at - {_WINDOW_SECONDS * 2} THEN 1 ELSE 0 END) AS prior_reviews
                FROM reviews r JOIN review_latest l ON l.steam_app_id = r.steam_app_id
                GROUP BY r.steam_app_id
            ),
            """
            review_join = "LEFT JOIN review_windows rw ON rw.steam_app_id = g.steam_app_id"
        dimensions = ""
        if include_dimensions and (optional["tags"] or optional["genres"]):
            sources: list[str] = []
            if optional["tags"]:
                sources.append("SELECT steam_app_id, 'tag' AS kind, LOWER(TRIM(value)) AS dimension, MIN(value COLLATE NOCASE) AS value FROM game_tags WHERE value IS NOT NULL AND TRIM(value) <> '' GROUP BY steam_app_id, LOWER(TRIM(value))")
            if optional["genres"]:
                sources.append("SELECT steam_app_id, 'genre' AS kind, LOWER(TRIM(value)) AS dimension, MIN(value COLLATE NOCASE) AS value FROM game_genres WHERE value IS NOT NULL AND TRIM(value) <> '' GROUP BY steam_app_id, LOWER(TRIM(value))")
            dimensions = "dimension_members AS (" + " UNION ALL ".join(sources) + "),"
        else:
            dimensions = "dimension_members AS (SELECT 0 AS steam_app_id, '' AS kind, '' AS dimension, '' AS value WHERE 0),"
        ctes = f"""
            {latest_market}
            {review_cte}
            base_games AS (
                SELECT g.steam_app_id, g.name,
                       {owner} AS owners_high, {peak} AS peak_ccu,
                       {reviews} AS review_count, {review_score} AS review_score,
                       {price} AS price_usd,
                       COALESCE(rw.recent_reviews, 0) AS recent_reviews,
                       COALESCE(rw.prior_reviews, 0) AS prior_reviews
                FROM games g {market_join} {summary_join} {review_join}
            ),
            maxima AS (
                SELECT MAX(owners_high) AS max_owners, MAX(peak_ccu) AS max_peak,
                       MAX(review_count) AS max_reviews, COUNT(*) AS total_games
                FROM base_games
            ),
            metrics AS (
                SELECT b.*,
                       CASE WHEN (b.owners_high > 0 OR b.peak_ccu > 0 OR b.review_count > 0) THEN
                           ((CASE WHEN b.owners_high > 0 AND x.max_owners > 0 THEN CAST(b.owners_high AS REAL) / x.max_owners ELSE 0 END)
                            + (CASE WHEN b.peak_ccu > 0 AND x.max_peak > 0 THEN CAST(b.peak_ccu AS REAL) / x.max_peak ELSE 0 END)
                            + (CASE WHEN b.review_count > 0 AND x.max_reviews > 0 THEN CAST(b.review_count AS REAL) / x.max_reviews ELSE 0 END))
                           / ((b.owners_high > 0) + (b.peak_ccu > 0) + (b.review_count > 0)) ELSE 0 END AS demand,
                       CASE WHEN b.recent_reviews + b.prior_reviews > 0 THEN
                           MAX(0.0, MIN(1.0, 0.5 + 0.5 * MAX(-1.0, MIN(1.0,
                           CAST(b.recent_reviews - b.prior_reviews AS REAL) / MAX(b.prior_reviews, 1))))) ELSE 0 END AS momentum
                FROM base_games b CROSS JOIN maxima x
            ),
            {dimensions}
            dimension_stats AS (
                SELECT d.kind, d.dimension, COUNT(*) AS member_count, AVG(m.demand) AS average_demand
                FROM dimension_members d JOIN metrics m ON m.steam_app_id = d.steam_app_id
                GROUP BY d.kind, d.dimension
            ),
            game_factors AS (
                SELECT d.steam_app_id,
                       AVG(s.average_demand) AS competition,
                       AVG(CAST(s.member_count - 1 AS REAL) / MAX(1, x.total_games - 1)) AS saturation,
                       ROUND(AVG(s.member_count - 1)) AS comparable_count
                FROM dimension_members d JOIN dimension_stats s
                  ON s.kind = d.kind AND s.dimension = d.dimension
                CROSS JOIN maxima x
                GROUP BY d.steam_app_id
            )
        """
        return ctes, optional

    def explore_trends(
        self,
        query: str | None = None,
        genre: str | None = None,
        tag: str | None = None,
        limit: int = 20,
    ) -> tuple[TrendResult, ...]:
        bounded_limit = _limit(limit)
        if bounded_limit == 0:
            return ()
        connection = self._open()
        if connection is None:
            return ()
        try:
            if not _table_exists(connection, "games"):
                return ()
            ctes, optional = self._base_sql(connection, include_dimensions=True)
            where = ["1 = 1"]
            params: list[object] = []
            if query and str(query).strip():
                where.append("m.name LIKE ? COLLATE NOCASE")
                params.append(f"%{str(query).strip()}%")
            for value, table, present in ((genre, "game_genres", optional["genres"]), (tag, "game_tags", optional["tags"])):
                if value and str(value).strip():
                    if not present:
                        return ()
                    where.append(
                        f"EXISTS (SELECT 1 FROM {table} f WHERE f.steam_app_id = m.steam_app_id AND LOWER(TRIM(f.value)) = LOWER(TRIM(?)))"
                    )
                    params.append(str(value).strip())
            sql = f"""
                WITH {ctes}
                SELECT m.*, COALESCE(f.competition, 0) AS competition,
                       COALESCE(f.saturation, 0) AS saturation,
                       COALESCE(f.comparable_count, 0) AS comparable_count,
                       ((m.demand * 0.35) + (m.momentum * 0.25)
                        + ((1 - COALESCE(f.competition, 0)) * 0.20)
                        + ((1 - COALESCE(f.saturation, 0)) * 0.20)) * 100 AS score
                FROM metrics m LEFT JOIN game_factors f ON f.steam_app_id = m.steam_app_id
                WHERE {' AND '.join(where)}
                ORDER BY score DESC, m.demand DESC, LOWER(m.name), m.steam_app_id
                LIMIT ?
            """
            params.append(bounded_limit)
            rows = connection.execute(sql, params).fetchall()
            app_ids = tuple(_integer(row["steam_app_id"]) for row in rows)
            tags = self._dimensions(connection, "game_tags", app_ids)
            genres = self._dimensions(connection, "game_genres", app_ids)
            results: list[TrendResult] = []
            for row in rows:
                app_id = _integer(row["steam_app_id"])
                factors = {
                    "demand": _bounded(row["demand"]),
                    "momentum": _bounded(row["momentum"]),
                    "competition": _bounded(row["competition"]),
                    "saturation": _bounded(row["saturation"]),
                }
                recent = _integer(row["recent_reviews"])
                prior = _integer(row["prior_reviews"])
                available = any(row[key] is not None and float(row[key]) > 0 for key in ("owners_high", "peak_ccu", "review_count"))
                results.append(
                    TrendResult(
                        app_id,
                        str(row["name"]),
                        _score(factors) if available else 0,
                        factors,
                        _integer(row["review_count"]),
                        recent,
                        prior,
                        tags.get(app_id, ()),
                        genres.get(app_id, ()),
                        _integer(row["comparable_count"]),
                        (
                            f"Demand combines available owner, peak-player, and review-volume signals ({'available' if available else 'unavailable'}).",
                            f"Momentum compares {recent:,} recent reviews with {prior:,} prior-window reviews.",
                            f"Competition averages demand across shared tag/genre groups ({_integer(row['comparable_count']):,} peers on average).",
                            f"Saturation compares those shared groups with the catalogue cohort.",
                        ),
                    )
                )
            return tuple(results)
        except sqlite3.DatabaseError:
            return ()
        finally:
            connection.close()

    def market_opportunities(
        self,
        dimension: str = "genre",
        limit: int = 20,
        genre: str | None = None,
        tag: str | None = None,
        *,
        kind: str | None = None,
    ) -> tuple[MarketOpportunity, ...]:
        bounded_limit = _limit(limit)
        dimension = _fold(kind if kind is not None else dimension)
        if bounded_limit == 0 or dimension not in {"genre", "tag"}:
            return ()
        connection = self._open()
        if connection is None:
            return ()
        try:
            if not _table_exists(connection, "games"):
                return ()
            ctes, optional = self._base_sql(connection, include_dimensions=True)
            filter_clauses = ["1 = 1"]
            params: list[object] = []
            for value, table, present in ((genre, "game_genres", optional["genres"]), (tag, "game_tags", optional["tags"])):
                if value and str(value).strip():
                    if not present:
                        return ()
                    filter_clauses.append(
                        f"EXISTS (SELECT 1 FROM {table} q WHERE q.steam_app_id = m.steam_app_id AND LOWER(TRIM(q.value)) = LOWER(TRIM(?)))"
                    )
                    params.append(str(value).strip())
            source = "genre" if dimension == "genre" else "tag"
            sql = f"""
                WITH {ctes},
                filtered_metrics AS (
                    SELECT m.* FROM metrics m WHERE {' AND '.join(filter_clauses)}
                ),
                selected_dimensions AS (
                    SELECT d.steam_app_id, d.dimension, d.value
                    FROM dimension_members d JOIN filtered_metrics m ON m.steam_app_id = d.steam_app_id
                    WHERE d.kind = ?
                ),
                grouped AS (
                    SELECT d.dimension, MIN(d.value COLLATE NOCASE) AS value, COUNT(*) AS matched_games,
                           AVG(m.demand) AS demand,
                           SUM(m.recent_reviews) AS recent_reviews,
                           SUM(m.prior_reviews) AS prior_reviews
                    FROM selected_dimensions d JOIN filtered_metrics m ON m.steam_app_id = d.steam_app_id
                    GROUP BY d.dimension
                ),
                max_group AS (SELECT MAX(matched_games) AS max_matched FROM grouped),
                totals AS (SELECT COUNT(*) AS total_games FROM filtered_metrics),
                scored AS (
                    SELECT g.*, t.total_games,
                           CASE WHEN g.recent_reviews + g.prior_reviews > 0 THEN
                               MAX(0.0, MIN(1.0, 0.5 + 0.5 * MAX(-1.0, MIN(1.0,
                               CAST(g.recent_reviews - g.prior_reviews AS REAL) / MAX(g.prior_reviews, 1))))) ELSE 0 END AS momentum,
                           CAST(g.matched_games - 1 AS REAL) / MAX(1, x.max_matched - 1) AS competition,
                           CAST(g.matched_games AS REAL) / MAX(1, t.total_games) AS saturation
                    FROM grouped g CROSS JOIN max_group x CROSS JOIN totals t
                )
                SELECT *,
                       ((demand * 0.35) + (momentum * 0.25)
                        + ((1 - competition) * 0.20) + ((1 - saturation) * 0.20)) * 100 AS score
                FROM scored
                ORDER BY score DESC, demand DESC, value COLLATE NOCASE, dimension
                LIMIT ?
            """
            params.extend((source, bounded_limit))
            rows = connection.execute(sql, params).fetchall()
            if not rows:
                return ()
            keys = tuple(str(row["dimension"]) for row in rows)
            placeholders = ",".join("?" for _ in keys)
            sample_sql = f"""
                WITH {ctes},
                filtered_metrics AS (SELECT m.* FROM metrics m WHERE {' AND '.join(filter_clauses)}),
                ranked AS (
                    SELECT d.dimension, m.name,
                           ROW_NUMBER() OVER (PARTITION BY d.dimension ORDER BY m.demand DESC, LOWER(m.name), m.steam_app_id) AS position
                    FROM dimension_members d JOIN filtered_metrics m ON m.steam_app_id = d.steam_app_id
                    WHERE d.kind = ? AND d.dimension IN ({placeholders})
                )
                SELECT dimension, name FROM ranked WHERE position <= 3 ORDER BY dimension, position
            """
            sample_params = list(params[:-2]) + [source, *keys]
            sample_rows = connection.execute(sample_sql, sample_params).fetchall()
            samples: dict[str, list[str]] = {}
            for row in sample_rows:
                samples.setdefault(str(row["dimension"]), []).append(str(row["name"]))
            results: list[MarketOpportunity] = []
            for row in rows:
                key = str(row["dimension"])
                value = str(row["value"])
                factors = {
                    "demand": _bounded(row["demand"]),
                    "momentum": _bounded(row["momentum"]),
                    "competition": _bounded(row["competition"]),
                    "saturation": _bounded(row["saturation"]),
                }
                matched = _integer(row["matched_games"])
                total = _integer(row["total_games"])
                recent = _integer(row["recent_reviews"])
                prior = _integer(row["prior_reviews"])
                results.append(
                    MarketOpportunity(
                        dimension,
                        value,
                        _score(factors),
                        factors,
                        matched,
                        total,
                        recent,
                        prior,
                        tuple(samples.get(key, ())),
                        (
                            f"{matched:,} real catalogue games carry this {dimension}.",
                            "Demand averages available owner, peak-player, and review-volume signals across those games.",
                            f"Momentum compares {recent:,} recent reviews with {prior:,} prior-window reviews.",
                            f"Competition is relative crowding among the {dimension} groups; saturation is {matched:,}/{total:,} catalogue games.",
                        ),
                    )
                )
            return tuple(results)
        except sqlite3.DatabaseError:
            return ()
        finally:
            connection.close()

    def genre_opportunities(self, limit: int = 20, tag: str | None = None) -> tuple[MarketOpportunity, ...]:
        return self.market_opportunities("genre", limit=limit, tag=tag)

    def tag_opportunities(self, limit: int = 20, genre: str | None = None) -> tuple[MarketOpportunity, ...]:
        return self.market_opportunities("tag", limit=limit, genre=genre)

    def comparable_games(self, steam_app_id: int, limit: int = 10) -> tuple[ComparableGame, ...]:
        bounded_limit = _limit(limit)
        if bounded_limit == 0:
            return ()
        connection = self._open()
        if connection is None:
            return ()
        try:
            if not _table_exists(connection, "games"):
                return ()
            game_columns = _columns(connection, "games")
            if not {"steam_app_id", "name"}.issubset(game_columns):
                return ()
            has_tags = _table_exists(connection, "game_tags")
            has_genres = _table_exists(connection, "game_genres")
            if not has_tags and not has_genres:
                return ()
            tag_cte = "target_tags AS (SELECT LOWER(TRIM(value)) AS dimension FROM game_tags WHERE steam_app_id = ? GROUP BY LOWER(TRIM(value)))," if has_tags else "target_tags AS (SELECT '' AS dimension WHERE 0),"
            genre_cte = "target_genres AS (SELECT LOWER(TRIM(value)) AS dimension FROM game_genres WHERE steam_app_id = ? GROUP BY LOWER(TRIM(value)))," if has_genres else "target_genres AS (SELECT '' AS dimension WHERE 0),"
            tag_overlap = """tag_overlap AS (
                SELECT gt.steam_app_id, COUNT(*) AS shared_tags
                FROM game_tags gt JOIN target_tags t ON t.dimension = LOWER(TRIM(gt.value))
                WHERE gt.steam_app_id <> ? GROUP BY gt.steam_app_id
            ),""" if has_tags else "tag_overlap AS (SELECT 0 AS steam_app_id, 0 AS shared_tags WHERE 0),"
            genre_overlap = """genre_overlap AS (
                SELECT gg.steam_app_id, COUNT(*) AS shared_genres
                FROM game_genres gg JOIN target_genres t ON t.dimension = LOWER(TRIM(gg.value))
                WHERE gg.steam_app_id <> ? GROUP BY gg.steam_app_id
            )""" if has_genres else "genre_overlap AS (SELECT 0 AS steam_app_id, 0 AS shared_genres WHERE 0)"
            total_reviews = "g.total_reviews" if "total_reviews" in game_columns else "0"
            review_score = "g.review_score" if "review_score" in game_columns else "NULL"
            price = "g.price_usd" if "price_usd" in game_columns else "NULL"
            sql = f"""
                WITH {tag_cte} {genre_cte} {tag_overlap} {genre_overlap}
                SELECT g.steam_app_id, g.name, COALESCE(t.shared_tags, 0) AS shared_tags,
                       COALESCE(n.shared_genres, 0) AS shared_genres,
                       {total_reviews} AS review_count, {review_score} AS review_score, {price} AS price_usd,
                       COALESCE(t.shared_tags, 0) * 2 + COALESCE(n.shared_genres, 0) AS overlap_score
                FROM games g LEFT JOIN tag_overlap t ON t.steam_app_id = g.steam_app_id
                             LEFT JOIN genre_overlap n ON n.steam_app_id = g.steam_app_id
                WHERE g.steam_app_id <> ? AND overlap_score > 0
                ORDER BY overlap_score DESC, review_count DESC, LOWER(g.name), g.steam_app_id
                LIMIT ?
            """
            # Target values are used once per target CTE; overlap CTEs and final
            # exclusion each receive the target ID as a bound parameter.
            params: list[object] = []
            if has_tags:
                params.append(int(steam_app_id))
            if has_genres:
                params.append(int(steam_app_id))
            if has_tags:
                params.append(int(steam_app_id))
            if has_genres:
                params.append(int(steam_app_id))
            params.extend((int(steam_app_id), bounded_limit))
            rows = connection.execute(sql, params).fetchall()
            app_ids = tuple(_integer(row["steam_app_id"]) for row in rows)
            target_tags = self._dimensions(connection, "game_tags", (int(steam_app_id),)).get(int(steam_app_id), ())
            target_genres = self._dimensions(connection, "game_genres", (int(steam_app_id),)).get(int(steam_app_id), ())
            target_tag_keys = {_fold(value): value for value in target_tags}
            target_genre_keys = {_fold(value): value for value in target_genres}
            tags = self._dimensions(connection, "game_tags", app_ids)
            genres = self._dimensions(connection, "game_genres", app_ids)
            results: list[ComparableGame] = []
            for row in rows:
                app_id = _integer(row["steam_app_id"])
                shared_tags = tuple(target_tag_keys[key] for key in sorted(target_tag_keys.keys() & {_fold(value) for value in tags.get(app_id, ())}))
                shared_genres = tuple(target_genre_keys[key] for key in sorted(target_genre_keys.keys() & {_fold(value) for value in genres.get(app_id, ())}))
                results.append(
                    ComparableGame(
                        app_id,
                        str(row["name"]),
                        _integer(row["overlap_score"]),
                        shared_tags,
                        shared_genres,
                        _integer(row["review_count"]),
                        _float_or_none(row["review_score"]),
                        _float_or_none(row["price_usd"]),
                        (f"Shares {len(shared_tags):,} tag(s) and {len(shared_genres):,} genre(s) with the selected game.",),
                    )
                )
            return tuple(results)
        except (sqlite3.DatabaseError, TypeError, ValueError):
            return ()
        finally:
            connection.close()


DeveloperIntelligenceService = DeveloperIntelligence


def explore_trends(database_path: Path, **filters) -> tuple[TrendResult, ...]:
    return DeveloperIntelligence(database_path).explore_trends(**filters)


def genre_opportunities(database_path: Path, **filters) -> tuple[MarketOpportunity, ...]:
    return DeveloperIntelligence(database_path).genre_opportunities(**filters)


def tag_opportunities(database_path: Path, **filters) -> tuple[MarketOpportunity, ...]:
    return DeveloperIntelligence(database_path).tag_opportunities(**filters)


def comparable_games(database_path: Path, steam_app_id: int, **filters) -> tuple[ComparableGame, ...]:
    return DeveloperIntelligence(database_path).comparable_games(steam_app_id, **filters)

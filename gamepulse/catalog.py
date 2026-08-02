"""Typed catalogue queries shared by all GamePulse prototype modes."""

import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class GameSummary:
    steam_app_id: int
    name: str
    release_date: str | None
    price_usd: float | None
    owners_low: int | None
    owners_high: int | None
    peak_ccu: int | None
    total_reviews: int | None
    review_score: float | None
    tags: tuple[str, ...]
    genres: tuple[str, ...]
    header_image_url: str | None
    windows: bool | None = None
    mac: bool | None = None
    linux: bool | None = None
    comparable_overlap: int = 0


@dataclass(frozen=True)
class PreferenceOptions:
    """Bounded, display-ready manual preference choices."""

    tags: tuple[str, ...]
    genres: tuple[str, ...]


class Catalog:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _summary(self, connection: sqlite3.Connection, row: sqlite3.Row) -> GameSummary:
        app_id = int(row["steam_app_id"])
        tags = tuple(item[0] for item in connection.execute("SELECT value FROM game_tags WHERE steam_app_id = ? ORDER BY value", (app_id,)))
        genres = tuple(item[0] for item in connection.execute("SELECT value FROM game_genres WHERE steam_app_id = ? ORDER BY value", (app_id,)))
        columns = set(row.keys())
        return GameSummary(
            app_id,
            row["name"],
            row["release_date"],
            row["price_usd"],
            row["owners_low"],
            row["owners_high"],
            row["peak_ccu"],
            row["total_reviews"],
            row["review_score"],
            tags,
            genres,
            row["header_image_url"],
            bool(row["windows"]) if "windows" in columns and row["windows"] is not None else None,
            bool(row["mac"]) if "mac" in columns and row["mac"] is not None else None,
            bool(row["linux"]) if "linux" in columns and row["linux"] is not None else None,
        )

    def _distinct_values(self, table: str, limit: int) -> tuple[str, ...]:
        """Return bounded, case-insensitively unique values from an internal table."""
        bounded_limit = max(1, min(int(limit), 1000))
        connection = self._connection()
        try:
            rows = connection.execute(
                f"SELECT MIN(TRIM(value)) AS value FROM {table} "
                "WHERE value IS NOT NULL AND TRIM(value) <> '' "
                "GROUP BY TRIM(value) COLLATE NOCASE "
                "ORDER BY value COLLATE NOCASE LIMIT ?",
                (bounded_limit,),
            ).fetchall()
        finally:
            connection.close()

        values: list[str] = []
        seen: set[str] = set()
        for row in rows:
            value = str(row["value"]).strip()
            folded = value.casefold()
            if folded in seen:
                continue
            seen.add(folded)
            values.append(value)
        return tuple(values)

    def preference_options(self, limit_per_group: int = 500) -> PreferenceOptions:
        """Return broad, case-insensitively unique tag and genre options."""
        return PreferenceOptions(
            tags=self._distinct_values("game_tags", limit_per_group),
            genres=self._distinct_values("game_genres", limit_per_group),
        )

    def comparable_games(self, steam_app_id: int, limit: int = 5) -> list[GameSummary]:
        """Return nearby games ranked by shared tags/genres and review volume."""
        target = self.get_game(steam_app_id)
        target_tags = {value.casefold() for value in target.tags}
        target_genres = {value.casefold() for value in target.genres}
        connection = self._connection()
        try:
            rows = connection.execute(
                "SELECT * FROM games WHERE steam_app_id <> ? ORDER BY COALESCE(total_reviews, 0) DESC, name LIMIT ?",
                (int(steam_app_id), max(1, min(int(limit) * 40, 500))),
            ).fetchall()
            ranked: list[tuple[int, int, str, GameSummary]] = []
            for row in rows:
                summary = self._summary(connection, row)
                shared_tags = len(target_tags & {value.casefold() for value in summary.tags})
                shared_genres = len(target_genres & {value.casefold() for value in summary.genres})
                overlap_score = shared_tags * 2 + shared_genres
                summary = replace(summary, comparable_overlap=overlap_score)
                ranked.append((overlap_score, summary.total_reviews or 0, summary.name.casefold(), summary))
        finally:
            connection.close()
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return [item[3] for item in ranked[: max(1, min(int(limit), 20))] if item[0] > 0]

    def search_games(self, query: str, limit: int = 20) -> list[GameSummary]:
        query = query.strip()
        if not query:
            return []
        connection = self._connection()
        try:
            rows = connection.execute("SELECT * FROM games WHERE name LIKE ? COLLATE NOCASE ORDER BY total_reviews DESC, name LIMIT ?", (f"%{query}%", max(1, min(limit, 100)))).fetchall()
            return [self._summary(connection, row) for row in rows]
        finally:
            connection.close()

    def get_game(self, steam_app_id: int) -> GameSummary:
        connection = self._connection()
        try:
            row = connection.execute("SELECT * FROM games WHERE steam_app_id = ?", (steam_app_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown Steam AppID: {steam_app_id}")
            return self._summary(connection, row)
        finally:
            connection.close()

    def rank_demo_candidates(self, limit: int = 20) -> list[GameSummary]:
        connection = self._connection()
        try:
            rows = connection.execute("""
                SELECT games.* FROM games
                JOIN review_summaries ON review_summaries.steam_app_id = games.steam_app_id
                AND review_summaries.review_count >= 500
                WHERE games.name NOT LIKE '%Playtest%' AND games.name NOT LIKE '%Demo%'
                ORDER BY
                    (CASE WHEN games.total_reviews >= 500 THEN 4 ELSE 0 END +
                     CASE WHEN games.owners_low IS NOT NULL AND games.owners_high IS NOT NULL THEN 2 ELSE 0 END +
                     CASE WHEN games.peak_ccu IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN games.review_score IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN games.price_usd IS NOT NULL THEN 1 ELSE 0 END) DESC,
                    review_summaries.review_count DESC,
                    games.steam_app_id
                LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
            return [self._summary(connection, row) for row in rows]
        finally:
            connection.close()

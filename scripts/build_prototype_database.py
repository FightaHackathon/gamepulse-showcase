"""Build the disposable local GamePulse prototype database from CSV outputs."""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamepulse.database import BuildReport, initialize_schema


def _number(value: str | None, kind: type = float):
    if value is None or value.strip() == "":
        return None
    try:
        return kind(value.replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _boolean(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(value.strip().lower() in {"true", "1", "yes"})


def _rows(path: Path):
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        yield from csv.DictReader(handle)


def _load_games(connection: sqlite3.Connection, processed_dir: Path) -> None:
    columns = ["steam_app_id", "name", "release_date", "price_usd", "discount_pct", "required_age", "owners_low", "owners_high", "peak_ccu", "positive_reviews", "negative_reviews", "total_reviews", "review_score", "recommendations", "average_playtime_minutes", "median_playtime_minutes", "windows", "mac", "linux", "metacritic_score", "header_image_url", "website_url", "short_description"]
    for row in _rows(processed_dir / "games_master.csv"):
        values = [row.get("steam_app_id"), row.get("name") or "Unknown"]
        for column in columns[2:]:
            value = row.get(column)
            if column in {"windows", "mac", "linux"}:
                value = _boolean(value)
            elif column in {"price_usd", "discount_pct", "review_score", "average_playtime_minutes", "median_playtime_minutes", "metacritic_score"}:
                value = _number(value)
            elif column in {"steam_app_id", "required_age", "owners_low", "owners_high", "peak_ccu", "positive_reviews", "negative_reviews", "total_reviews", "recommendations"}:
                value = _number(value, int)
            values.append(value)
        connection.execute(f"INSERT INTO games ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", values)


def _load_bridge(connection: sqlite3.Connection, processed_dir: Path, filename: str, table: str) -> None:
    for row in _rows(processed_dir / filename):
        app_id = _number(row.get("steam_app_id"), int)
        value = (row.get("value") or "").strip()
        if app_id is not None and value:
            connection.execute(f"INSERT OR IGNORE INTO {table} (steam_app_id, value) VALUES (?, ?)", (app_id, value))


def _load_summaries(connection: sqlite3.Connection, processed_dir: Path) -> None:
    columns = ["steam_app_id", "review_count", "recommended_count", "not_recommended_count", "review_score", "helpful_votes_total", "funny_votes_total", "average_word_count", "average_playtime_minutes", "latest_review_created_at_unix"]
    for row in _rows(processed_dir / "game_review_summary.csv"):
        values = []
        for column in columns:
            value = row.get(column)
            value = _number(value, int) if column in {"steam_app_id", "review_count", "recommended_count", "not_recommended_count", "helpful_votes_total", "funny_votes_total", "latest_review_created_at_unix"} else _number(value)
            values.append(value)
        if values[0] is not None and connection.execute("SELECT 1 FROM games WHERE steam_app_id = ?", (values[0],)).fetchone():
            connection.execute(f"INSERT OR REPLACE INTO review_summaries ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", values)


def _load_reviews(connection: sqlite3.Connection, processed_dir: Path) -> None:
    columns = ["review_id", "steam_app_id", "review_text", "word_count", "recommended", "helpful_votes", "funny_votes", "created_at_unix", "author_playtime_minutes", "source_game_name", "source_price", "source_release_date"]
    valid_app_ids = {row[0] for row in connection.execute("SELECT steam_app_id FROM games")}
    with (processed_dir / "reviews_clean.csv").open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        batch = []
        for row in reader:
            values = [row.get("review_id"), _number(row.get("steam_app_id"), int), row.get("review_text") or "", _number(row.get("word_count"), int), _boolean(row.get("recommended")), _number(row.get("helpful_votes"), int), _number(row.get("funny_votes"), int), _number(row.get("created_at_unix"), int), _number(row.get("author_playtime_minutes"), int), row.get("source_game_name"), _number(row.get("source_price")), row.get("source_release_date")]
            if values[0] and values[1] in valid_app_ids and values[2]:
                batch.append(values)
            if len(batch) >= 2000:
                connection.executemany(f"INSERT OR IGNORE INTO reviews ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", batch)
                batch.clear()
        if batch:
            connection.executemany(f"INSERT OR IGNORE INTO reviews ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", batch)


def build_database(processed_dir: Path, database_path: Path) -> BuildReport:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="gamepulse-", suffix=".sqlite3", dir=database_path.parent, delete=False) as handle:
        temporary_path = Path(handle.name)
    connection = None
    try:
        connection = sqlite3.connect(temporary_path)
        connection.execute("PRAGMA foreign_keys = ON")
        initialize_schema(connection)
        _load_games(connection, processed_dir)
        _load_bridge(connection, processed_dir, "game_tags.csv", "game_tags")
        _load_bridge(connection, processed_dir, "game_genres.csv", "game_genres")
        _load_summaries(connection, processed_dir)
        _load_reviews(connection, processed_dir)
        connection.commit()
        foreign_keys_ok = not connection.execute("PRAGMA foreign_key_check").fetchall()
        table_names = ["games", "game_tags", "game_genres", "review_summaries", "reviews"]
        counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in table_names}
        connection.close()
        connection = None
        if not foreign_keys_ok:
            raise ValueError("prototype database failed foreign-key validation")
        os.replace(temporary_path, database_path)
        return BuildReport(table_counts=counts, foreign_keys_ok=foreign_keys_ok)
    finally:
        if connection is not None:
            connection.close()
        if temporary_path.exists():
            temporary_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-dir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    report = build_database(args.processed_dir, args.database)
    print(report)


if __name__ == "__main__":
    main()

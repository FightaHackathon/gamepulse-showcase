import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from gamepulse.db.importer import SqlAlchemyImportRepository, import_sqlite
from gamepulse.db.models import Base, GameModel, GameTagModel, ReviewSummaryModel, SteamSnapshotModel


def build_source(path: Path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE games (
            steam_app_id INTEGER PRIMARY KEY, name TEXT NOT NULL, release_date TEXT,
            price_usd REAL, discount_pct REAL, required_age INTEGER,
            owners_low INTEGER, owners_high INTEGER, peak_ccu INTEGER,
            positive_reviews INTEGER, negative_reviews INTEGER, total_reviews INTEGER,
            review_score REAL, recommendations INTEGER, average_playtime_minutes REAL,
            median_playtime_minutes REAL, windows INTEGER, mac INTEGER, linux INTEGER,
            metacritic_score REAL, header_image_url TEXT, website_url TEXT, short_description TEXT
        );
        CREATE TABLE game_tags (steam_app_id INTEGER NOT NULL, value TEXT NOT NULL);
        CREATE TABLE game_genres (steam_app_id INTEGER NOT NULL, value TEXT NOT NULL);
        CREATE TABLE review_summaries (
            steam_app_id INTEGER PRIMARY KEY, review_count INTEGER, recommended_count INTEGER,
            not_recommended_count INTEGER, review_score REAL, helpful_votes_total INTEGER,
            funny_votes_total INTEGER, average_word_count REAL, average_playtime_minutes REAL,
            latest_review_created_at_unix INTEGER
        );
        CREATE TABLE steam_market_snapshots (
            observed_at TEXT NOT NULL, steam_app_id INTEGER NOT NULL, seller_rank INTEGER,
            peak_ccu INTEGER, owners_low INTEGER, owners_high INTEGER, total_reviews INTEGER,
            price_usd REAL, discount_pct REAL, player_metric TEXT, source_mode TEXT,
            source_name TEXT, source_url TEXT, collection_method TEXT, confidence TEXT
        );
        """
    )
    connection.executemany(
        "INSERT INTO games (steam_app_id, name, price_usd, owners_low, owners_high, review_score, header_image_url, windows) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (10, "Counter-Strike", 0.0, 1000, 2000, 0.91, "https://example.test/10.jpg", 1),
            (20, "Game Two", 19.99, 500, 900, 0.82, "https://example.test/20.jpg", 1),
        ],
    )
    connection.executemany("INSERT INTO game_tags VALUES (?, ?)", [(10, "Action"), (10, "FPS"), (20, "Indie")])
    connection.executemany("INSERT INTO game_genres VALUES (?, ?)", [(10, "Action"), (20, "Adventure")])
    connection.execute("INSERT INTO review_summaries VALUES (10, 100, 90, 10, 0.9, 5, 2, 20, 1000, 123456)")
    connection.execute(
        "INSERT INTO steam_market_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2026-08-08T06:00:00+00:00", 10, 1, 1500, 1000, 2000, 100, 0.0, 0.0, "peak", "imported", "Prototype", "https://example.test/source", "fixture", "medium"),
    )
    connection.commit()
    connection.close()


def test_importer_preserves_core_fields_and_is_idempotent(tmp_path):
    source = tmp_path / "source.sqlite3"
    build_source(source)
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = SqlAlchemyImportRepository(session)
        first = import_sqlite(source, repository)
        second = import_sqlite(source, repository)

        game = session.get(GameModel, 10)
        assert game is not None
        assert game.header_image_url == "https://example.test/10.jpg"
        assert game.review_score == 0.91
        assert (game.owners_low, game.owners_high) == (1000, 2000)
        assert session.scalar(select(func.count()).select_from(GameModel)) == 2
        assert session.scalar(select(func.count()).select_from(GameTagModel)) == 3
        assert session.scalar(select(func.count()).select_from(ReviewSummaryModel)) == 1
        assert session.scalar(select(func.count()).select_from(SteamSnapshotModel)) == 4
        assert first.row_counts["games"] == 2
        assert second.validation_failures == ()

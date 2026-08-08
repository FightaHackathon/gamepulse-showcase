import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, func, select
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
from gamepulse.jobs.import_full_database import run_full_import


def build_full_source(path: Path) -> None:
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
        CREATE TABLE reviews (
            review_id TEXT PRIMARY KEY, steam_app_id INTEGER NOT NULL, review_text TEXT NOT NULL,
            word_count INTEGER, recommended INTEGER, helpful_votes INTEGER, funny_votes INTEGER,
            created_at_unix INTEGER, author_playtime_minutes INTEGER, source_game_name TEXT,
            source_price REAL, source_release_date TEXT
        );
        CREATE TABLE steam_market_snapshots (
            observed_at TEXT NOT NULL, steam_app_id INTEGER NOT NULL, seller_rank INTEGER,
            peak_ccu INTEGER, owners_low INTEGER, owners_high INTEGER, total_reviews INTEGER,
            price_usd REAL, discount_pct REAL, player_metric TEXT, source_mode TEXT,
            source_name TEXT, source_url TEXT, collection_method TEXT, confidence TEXT
        );
        CREATE TABLE twitch_game_snapshots (
            observed_at TEXT NOT NULL, game_id TEXT, game_name TEXT, viewer_count INTEGER,
            channel_count INTEGER, source_mode TEXT, source_name TEXT
        );
        """
    )
    connection.executemany(
        "INSERT INTO games (steam_app_id, name, release_date, price_usd, peak_ccu, total_reviews, review_score, header_image_url, short_description, windows) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (10, "Counter-Strike", "2000-11-01", 0.0, 1500, 100, 0.91, "https://example.test/10.jpg", "FPS", 1),
            (20, "Game Two", "2024-01-01", 19.99, 500, 50, 0.82, "https://example.test/20.jpg", "Indie", 1),
        ],
    )
    connection.executemany("INSERT INTO game_tags VALUES (?, ?)", [(10, "Action"), (10, "FPS"), (20, "Indie")])
    connection.executemany("INSERT INTO game_genres VALUES (?, ?)", [(10, "Action"), (20, "Adventure")])
    connection.execute("INSERT INTO review_summaries VALUES (10, 100, 90, 10, 0.9, 5, 2, 20, 1000, 123456)")
    connection.executemany(
        "INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("review-1", 10, "Great game", 2, 1, 3, 1, 123456, 1000, "Counter-Strike", 0.0, "2000-11-01"),
            ("review-2", 10, "Needs work", 2, 0, 1, 0, 123457, 500, "Counter-Strike", 0.0, "2000-11-01"),
        ],
    )
    connection.execute(
        "INSERT INTO steam_market_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2026-08-01T18:32:17Z", 10, 1, 1500, 1000, 2000, 100, 0.0, 0.0, "peak", "Live", "Steam + SteamSpy", "https://example.test/source", "fixture", "mixed-public"),
    )
    connection.execute(
        "INSERT INTO twitch_game_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-08-01T18:32:17Z", "10", "Counter-Strike", 250, 5, "public_30d_summary", "TwitchTracker"),
    )
    connection.commit()
    connection.close()


def counts(session: Session) -> dict[str, int]:
    return {
        "games": session.scalar(select(func.count()).select_from(GameModel)),
        "game_tags": session.scalar(select(func.count()).select_from(GameTagModel)),
        "game_genres": session.scalar(select(func.count()).select_from(GameGenreModel)),
        "review_summaries": session.scalar(select(func.count()).select_from(ReviewSummaryModel)),
        "reviews": session.scalar(select(func.count()).select_from(ReviewModel)),
        "steam_snapshots": session.scalar(select(func.count()).select_from(SteamSnapshotModel)),
        "streaming_snapshots": session.scalar(select(func.count()).select_from(StreamingSnapshotModel)),
        "steamspy_snapshots": session.scalar(select(func.count()).select_from(SteamSpySnapshotModel)),
        "trend_scores": session.scalar(select(func.count()).select_from(TrendScoreModel)),
        "provider_runs": session.scalar(select(func.count()).select_from(ProviderRunModel)),
    }


def test_full_import_preserves_all_available_tables_and_is_idempotent(tmp_path):
    source = tmp_path / "source.sqlite3"
    target = tmp_path / "target.sqlite3"
    build_full_source(source)
    target_url = f"sqlite+pysqlite:///{target}"

    engine = create_engine(target_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    first = run_full_import(source, target_url, observed_at="2026-08-01T18:32:17Z", batch_size=2)
    second = run_full_import(source, target_url, observed_at="2026-08-01T18:32:17Z", batch_size=2)

    engine = create_engine(target_url)
    with Session(engine) as session:
        actual = counts(session)
        assert actual == {
            "games": 2,
            "game_tags": 3,
            "game_genres": 2,
            "review_summaries": 1,
            "reviews": 2,
            "steam_snapshots": 4,
            "streaming_snapshots": 2,
            "steamspy_snapshots": 1,
            "trend_scores": 5,
            "provider_runs": 2,
        }
        review = session.get(ReviewModel, "review-1")
        assert review is not None
        assert review.source_name == "GamePulse prototype SQLite"
        assert review.source_mode == "historical_import"
        assert session.scalar(select(func.count()).select_from(TrendScoreModel).where(TrendScoreModel.audience == "streamer")) == 1

    assert first.row_counts == second.row_counts
    assert first.validation_failures == ()
    assert second.validation_failures == ()
    engine.dispose()

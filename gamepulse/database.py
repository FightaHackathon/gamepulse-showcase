"""SQLite schema and read-only connections for the disposable prototype DB."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BuildReport:
    table_counts: dict[str, int]
    foreign_keys_ok: bool


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE games (
    steam_app_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    release_date TEXT,
    price_usd REAL,
    discount_pct REAL,
    required_age INTEGER,
    owners_low INTEGER,
    owners_high INTEGER,
    peak_ccu INTEGER,
    positive_reviews INTEGER,
    negative_reviews INTEGER,
    total_reviews INTEGER,
    review_score REAL,
    recommendations INTEGER,
    average_playtime_minutes REAL,
    median_playtime_minutes REAL,
    windows INTEGER,
    mac INTEGER,
    linux INTEGER,
    metacritic_score REAL,
    header_image_url TEXT,
    website_url TEXT,
    short_description TEXT
);
CREATE TABLE game_tags (steam_app_id INTEGER NOT NULL, value TEXT NOT NULL, PRIMARY KEY (steam_app_id, value), FOREIGN KEY (steam_app_id) REFERENCES games(steam_app_id));
CREATE TABLE game_genres (steam_app_id INTEGER NOT NULL, value TEXT NOT NULL, PRIMARY KEY (steam_app_id, value), FOREIGN KEY (steam_app_id) REFERENCES games(steam_app_id));
CREATE TABLE review_summaries (
    steam_app_id INTEGER PRIMARY KEY,
    review_count INTEGER NOT NULL DEFAULT 0,
    recommended_count INTEGER NOT NULL DEFAULT 0,
    not_recommended_count INTEGER NOT NULL DEFAULT 0,
    review_score REAL,
    helpful_votes_total INTEGER,
    funny_votes_total INTEGER,
    average_word_count REAL,
    average_playtime_minutes REAL,
    latest_review_created_at_unix INTEGER,
    FOREIGN KEY (steam_app_id) REFERENCES games(steam_app_id)
);
CREATE TABLE reviews (
    review_id TEXT PRIMARY KEY,
    steam_app_id INTEGER NOT NULL,
    review_text TEXT NOT NULL,
    word_count INTEGER,
    recommended INTEGER,
    helpful_votes INTEGER,
    funny_votes INTEGER,
    created_at_unix INTEGER,
    author_playtime_minutes INTEGER,
    source_game_name TEXT,
    source_price REAL,
    source_release_date TEXT,
    FOREIGN KEY (steam_app_id) REFERENCES games(steam_app_id)
);
CREATE TABLE twitch_game_snapshots (
    observed_at TEXT NOT NULL,
    game_id TEXT NOT NULL,
    game_name TEXT NOT NULL,
    steam_app_id INTEGER,
    rank INTEGER,
    viewer_count INTEGER,
    channel_count INTEGER,
    viewer_to_channel REAL,
    top_one_viewer_share REAL,
    top_five_viewer_share REAL,
    average_stream_age_seconds REAL,
    growth_score REAL,
    coverage_stream_count INTEGER NOT NULL DEFAULT 0,
    coverage_page_count INTEGER NOT NULL DEFAULT 0,
    partial_coverage INTEGER NOT NULL DEFAULT 0,
    observed_total INTEGER NOT NULL DEFAULT 0,
    source_mode TEXT NOT NULL,
    source_name TEXT NOT NULL,
    PRIMARY KEY (observed_at, game_id)
);
CREATE TABLE twitch_streamer_snapshots (
    observed_at TEXT NOT NULL,
    stream_id TEXT NOT NULL,
    streamer_id TEXT NOT NULL,
    streamer_name TEXT NOT NULL,
    streamer_login TEXT,
    game_id TEXT,
    game_name TEXT,
    viewer_count INTEGER,
    language TEXT,
    title TEXT,
    start_time TEXT,
    tags_json TEXT NOT NULL DEFAULT '[]',
    channel_size_tier TEXT,
    broadcaster_type TEXT,
    profile_image_url TEXT,
    category_rank INTEGER,
    source_mode TEXT NOT NULL,
    source_name TEXT NOT NULL,
    PRIMARY KEY (observed_at, stream_id)
);
CREATE TABLE twitch_game_mappings (
    twitch_game_id TEXT PRIMARY KEY,
    twitch_name TEXT NOT NULL,
    steam_app_id INTEGER,
    steam_name TEXT,
    match_method TEXT NOT NULL,
    match_score REAL NOT NULL DEFAULT 0,
    manual_verified INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE steam_market_snapshots (observed_at TEXT NOT NULL, steam_app_id INTEGER NOT NULL, seller_rank INTEGER, peak_ccu INTEGER, owners_low INTEGER, owners_high INTEGER, total_reviews INTEGER, price_usd REAL, discount_pct REAL, player_metric TEXT NOT NULL DEFAULT 'peak', source_mode TEXT NOT NULL, source_name TEXT NOT NULL, source_url TEXT, collection_method TEXT, confidence TEXT, PRIMARY KEY (observed_at, steam_app_id));
CREATE INDEX games_name_search ON games(name COLLATE NOCASE);
CREATE INDEX reviews_game_created ON reviews(steam_app_id, created_at_unix);
CREATE INDEX twitch_games_observed ON twitch_game_snapshots(observed_at);
CREATE INDEX twitch_games_game_observed ON twitch_game_snapshots(game_id, observed_at);
CREATE INDEX twitch_games_rank ON twitch_game_snapshots(observed_at, rank);
CREATE INDEX twitch_streamers_observed ON twitch_streamer_snapshots(observed_at);
CREATE INDEX twitch_streamers_game_observed ON twitch_streamer_snapshots(game_id, observed_at);
CREATE INDEX twitch_streamers_streamer_observed ON twitch_streamer_snapshots(streamer_id, observed_at);
CREATE INDEX twitch_game_mappings_steam ON twitch_game_mappings(steam_app_id);
CREATE INDEX twitch_game_mappings_updated ON twitch_game_mappings(updated_at);
CREATE INDEX market_app_observed ON steam_market_snapshots(steam_app_id, observed_at);
"""


def connect_read_only(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{database_path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)


_TWITCH_GAME_COLUMNS = {
    "steam_app_id": "INTEGER",
    "rank": "INTEGER",
    "viewer_to_channel": "REAL",
    "top_one_viewer_share": "REAL",
    "top_five_viewer_share": "REAL",
    "average_stream_age_seconds": "REAL",
    "growth_score": "REAL",
    "coverage_stream_count": "INTEGER NOT NULL DEFAULT 0",
    "coverage_page_count": "INTEGER NOT NULL DEFAULT 0",
    "partial_coverage": "INTEGER NOT NULL DEFAULT 0",
    "observed_total": "INTEGER NOT NULL DEFAULT 0",
}

_TWITCH_STREAMER_COLUMNS = {
    "stream_id": "TEXT NOT NULL DEFAULT ''",
    "streamer_login": "TEXT",
    "title": "TEXT",
    "start_time": "TEXT",
    "tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "broadcaster_type": "TEXT",
    "profile_image_url": "TEXT",
    "category_rank": "INTEGER",
}


def ensure_twitch_snapshot_schema(connection: sqlite3.Connection) -> None:
    """Create or migrate only the Twitch snapshot tables for collection runs."""
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS twitch_game_snapshots (
            observed_at TEXT NOT NULL,
            game_id TEXT NOT NULL,
            game_name TEXT NOT NULL,
            steam_app_id INTEGER,
            rank INTEGER,
            viewer_count INTEGER,
            channel_count INTEGER,
            viewer_to_channel REAL,
            top_one_viewer_share REAL,
            top_five_viewer_share REAL,
            average_stream_age_seconds REAL,
            growth_score REAL,
            coverage_stream_count INTEGER NOT NULL DEFAULT 0,
            coverage_page_count INTEGER NOT NULL DEFAULT 0,
            partial_coverage INTEGER NOT NULL DEFAULT 0,
            observed_total INTEGER NOT NULL DEFAULT 0,
            source_mode TEXT NOT NULL,
            source_name TEXT NOT NULL,
            PRIMARY KEY (observed_at, game_id)
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS twitch_streamer_snapshots (
            observed_at TEXT NOT NULL,
            stream_id TEXT NOT NULL,
            streamer_id TEXT NOT NULL,
            streamer_name TEXT NOT NULL,
            streamer_login TEXT,
            game_id TEXT,
            game_name TEXT,
            viewer_count INTEGER,
            language TEXT,
            title TEXT,
            start_time TEXT,
            tags_json TEXT NOT NULL DEFAULT '[]',
            channel_size_tier TEXT,
            broadcaster_type TEXT,
            profile_image_url TEXT,
            category_rank INTEGER,
            source_mode TEXT NOT NULL,
            source_name TEXT NOT NULL,
            PRIMARY KEY (observed_at, stream_id)
        )"""
    )
    for table, columns in (("twitch_game_snapshots", _TWITCH_GAME_COLUMNS), ("twitch_streamer_snapshots", _TWITCH_STREAMER_COLUMNS)):
        existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        for column, definition in columns.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    connection.executescript(
        """CREATE INDEX IF NOT EXISTS twitch_games_observed ON twitch_game_snapshots(observed_at);
        CREATE INDEX IF NOT EXISTS twitch_games_game_observed ON twitch_game_snapshots(game_id, observed_at);
        CREATE INDEX IF NOT EXISTS twitch_games_rank ON twitch_game_snapshots(observed_at, rank);
        CREATE INDEX IF NOT EXISTS twitch_streamers_observed ON twitch_streamer_snapshots(observed_at);
        CREATE INDEX IF NOT EXISTS twitch_streamers_game_observed ON twitch_streamer_snapshots(game_id, observed_at);
        CREATE INDEX IF NOT EXISTS twitch_streamers_streamer_observed ON twitch_streamer_snapshots(streamer_id, observed_at);"""
    )


_TWITCH_GAME_MAPPING_COLUMNS = {
    "twitch_name": "TEXT NOT NULL DEFAULT ''",
    "steam_app_id": "INTEGER",
    "steam_name": "TEXT",
    "match_method": "TEXT NOT NULL DEFAULT 'unmatched'",
    "match_score": "REAL NOT NULL DEFAULT 0",
    "manual_verified": "INTEGER NOT NULL DEFAULT 0",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
}


def ensure_twitch_game_mapping_schema(connection: sqlite3.Connection) -> None:
    """Create or migrate the Twitch-to-Steam mapping table for collection runs."""
    connection.execute(
        """CREATE TABLE IF NOT EXISTS twitch_game_mappings (
            twitch_game_id TEXT PRIMARY KEY,
            twitch_name TEXT NOT NULL,
            steam_app_id INTEGER,
            steam_name TEXT,
            match_method TEXT NOT NULL,
            match_score REAL NOT NULL DEFAULT 0,
            manual_verified INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )"""
    )
    existing = {row[1] for row in connection.execute("PRAGMA table_info(twitch_game_mappings)")}
    for column, definition in _TWITCH_GAME_MAPPING_COLUMNS.items():
        if column not in existing:
            connection.execute(f"ALTER TABLE twitch_game_mappings ADD COLUMN {column} {definition}")
    connection.executescript(
        """CREATE INDEX IF NOT EXISTS twitch_game_mappings_steam ON twitch_game_mappings(steam_app_id);
        CREATE INDEX IF NOT EXISTS twitch_game_mappings_updated ON twitch_game_mappings(updated_at);"""
    )

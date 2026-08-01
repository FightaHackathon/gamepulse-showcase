"""Collect one bounded public Steam market snapshot into the prototype DB."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamepulse.providers.steam_market import PublicSteamMarketProvider
from gamepulse.market_analysis import MarketSnapshot


def _ensure_snapshot_columns(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(steam_market_snapshots)").fetchall()}
    if "player_metric" not in columns:
        connection.execute("ALTER TABLE steam_market_snapshots ADD COLUMN player_metric TEXT NOT NULL DEFAULT 'peak'")


def save_snapshot(connection: sqlite3.Connection, snapshot: MarketSnapshot) -> None:
    _ensure_snapshot_columns(connection)
    connection.execute(
        """INSERT OR REPLACE INTO steam_market_snapshots
        (observed_at, steam_app_id, seller_rank, peak_ccu, owners_low, owners_high,
         total_reviews, price_usd, discount_pct, player_metric, source_mode, source_name,
         source_url, collection_method, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (snapshot.observed_at, snapshot.steam_app_id, snapshot.seller_rank, snapshot.peak_ccu,
         snapshot.owners_low, snapshot.owners_high, snapshot.total_reviews, snapshot.price_usd,
         snapshot.discount_pct, snapshot.player_metric, snapshot.source_mode, snapshot.source_name, snapshot.source_url,
         snapshot.collection_method, snapshot.confidence),
    )


def collect_and_save(database_path: Path, app_id: int, provider: PublicSteamMarketProvider | None = None) -> MarketSnapshot:
    snapshot = (provider or PublicSteamMarketProvider()).collect(app_id)
    connection = sqlite3.connect(database_path)
    try:
        save_snapshot(connection, snapshot)
        connection.commit()
    finally:
        connection.close()
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--app-id", type=int, required=True)
    args = parser.parse_args()
    snapshot = collect_and_save(args.database, args.app_id)
    print(snapshot)


if __name__ == "__main__":
    main()

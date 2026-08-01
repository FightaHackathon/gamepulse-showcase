import unittest
import sqlite3
import tempfile
from pathlib import Path

from gamepulse.market_analysis import MarketSnapshot, analyze_market, latest_market_snapshot
from gamepulse.providers.steam_market import PublicSteamMarketProvider
from scripts.collect_public_market_snapshot import save_snapshot


class MarketAnalysisTests(unittest.TestCase):
    def test_estimated_revenue_is_a_range_and_keeps_verified_rank_separate(self):
        snapshot = MarketSnapshot(10, seller_rank=4, owners_low=1000, owners_high=2000, price_usd=20.0, total_reviews=100, peak_ccu=50, source_mode="Demo", source_name="fixture", observed_at="2026-08-01T00:00:00Z")

        analysis = analyze_market(snapshot, comparable_games=[{"name": "Comparable", "review_score": 0.9}])

        self.assertEqual(analysis.seller_rank, 4)
        self.assertLessEqual(analysis.estimated_gross_low, analysis.estimated_gross_high)
        self.assertIn("estimated", analysis.disclaimer.lower())

    def test_public_provider_keeps_official_and_estimated_fields_distinct(self):
        responses = {
            "store": {"10": {"success": True, "data": {"price_overview": {"final": 1999, "discount_percent": 10}, "recommendations": {"total": 1200}}}},
            "players": {"response": {"player_count": 321}},
            "steamspy": {"owners": "1,000 .. 2,000", "players_forever": 777},
        }

        provider = PublicSteamMarketProvider(fetch_json=lambda source, app_id: responses[source])
        snapshot = provider.collect(10)

        self.assertEqual(snapshot.peak_ccu, 321)
        self.assertEqual(snapshot.player_metric, "current")
        self.assertEqual(snapshot.discount_pct, 10.0)
        self.assertEqual(snapshot.total_reviews, 1200)
        self.assertEqual(snapshot.owners_low, 1000)
        self.assertEqual(snapshot.owners_high, 2000)
        self.assertEqual(snapshot.source_mode, "Live")
        self.assertIn("Steam Store", snapshot.source_name)
        self.assertEqual(snapshot.confidence, "mixed-public")

    def test_prepared_snapshot_defaults_to_peak_player_metric(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "market.sqlite3"
            connection = sqlite3.connect(database)
            connection.executescript("""
                CREATE TABLE steam_market_snapshots (
                    observed_at TEXT NOT NULL, steam_app_id INTEGER NOT NULL, seller_rank INTEGER,
                    peak_ccu INTEGER, owners_low INTEGER, owners_high INTEGER, total_reviews INTEGER,
                    price_usd REAL, discount_pct REAL, source_mode TEXT NOT NULL, source_name TEXT NOT NULL,
                    source_url TEXT, collection_method TEXT, confidence TEXT,
                    PRIMARY KEY (observed_at, steam_app_id)
                )
            """)
            connection.execute("INSERT INTO steam_market_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("2026-08-01T00:00:00Z", 10, None, 50, 1000, 2000, 100, 20.0, 0, "Local", "prepared", None, "method", "known"))
            connection.commit()
            connection.close()
            snapshot = latest_market_snapshot(database, 10)
        self.assertEqual(snapshot.player_metric, "peak")

    def test_snapshot_persistence_keeps_provenance_fields(self):
        snapshot = MarketSnapshot(
            10,
            4,
            1000,
            2000,
            20.0,
            100,
            50,
            "Live",
            "fixture",
            "2026-08-01T00:00:00Z",
            "https://example.test",
            "fixture JSON",
            "mixed-public",
            discount_pct=10.0,
            player_metric="current",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "market.sqlite3"
            connection = sqlite3.connect(database)
            connection.executescript("""
                CREATE TABLE steam_market_snapshots (
                    observed_at TEXT NOT NULL, steam_app_id INTEGER NOT NULL, seller_rank INTEGER,
                    peak_ccu INTEGER, owners_low INTEGER, owners_high INTEGER, total_reviews INTEGER,
                    price_usd REAL, discount_pct REAL, source_mode TEXT NOT NULL, source_name TEXT NOT NULL,
                    source_url TEXT, collection_method TEXT, confidence TEXT,
                    PRIMARY KEY (observed_at, steam_app_id)
                )
            """)
            save_snapshot(connection, snapshot)
            row = connection.execute("SELECT source_url, collection_method, confidence, discount_pct, player_metric FROM steam_market_snapshots").fetchone()
            connection.close()
        self.assertEqual(row, ("https://example.test", "fixture JSON", "mixed-public", 10.0, "current"))

    def test_latest_snapshot_reads_the_most_recent_observation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "market.sqlite3"
            connection = sqlite3.connect(database)
            connection.executescript("""
                CREATE TABLE steam_market_snapshots (
                    observed_at TEXT NOT NULL, steam_app_id INTEGER NOT NULL, seller_rank INTEGER,
                    peak_ccu INTEGER, owners_low INTEGER, owners_high INTEGER, total_reviews INTEGER,
                    price_usd REAL, discount_pct REAL, source_mode TEXT NOT NULL, source_name TEXT NOT NULL,
                    source_url TEXT, collection_method TEXT, confidence TEXT,
                    PRIMARY KEY (observed_at, steam_app_id)
                )
            """)
            connection.execute("INSERT INTO steam_market_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("2026-08-01T00:00:00Z", 10, 4, 50, 1000, 2000, 100, 20.0, 0, "Live", "new", "url", "method", "mixed-public"))
            connection.commit()
            connection.close()
            snapshot = latest_market_snapshot(database, 10)
        self.assertEqual(snapshot.source_name, "new")
        self.assertEqual(snapshot.owners_high, 2000)


if __name__ == "__main__":
    unittest.main()

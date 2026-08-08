import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gamepulse.database import SCHEMA
import gamepulse.developer_intelligence as intelligence_module
from gamepulse.developer_intelligence import DeveloperIntelligence


class DeveloperIntelligenceTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        path = root / "intelligence.sqlite3"
        connection = sqlite3.connect(path)
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO games (steam_app_id, name, owners_high, peak_ccu, total_reviews, review_score) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (10, "Alpha Quest", 100000, 1000, 1000, 0.90),
                (20, "Beta Builder", 20000, 250, 400, 0.85),
                (30, "Gamma Tactics", 5000, 100, 100, 0.80),
                (40, "Delta Solo", 1000, 10, 20, 0.70),
            ],
        )
        connection.executemany(
            "INSERT INTO game_tags VALUES (?, ?)",
            [(10, "Co-op"), (10, "RPG"), (20, "Co-op"), (20, "Builder"), (30, "RPG")],
        )
        connection.executemany(
            "INSERT INTO game_genres VALUES (?, ?)",
            [(10, "Action"), (20, "Simulation"), (30, "Action"), (40, "Puzzle")],
        )
        connection.executemany(
            "INSERT INTO reviews (review_id, steam_app_id, review_text, created_at_unix) VALUES (?, ?, ?, ?)",
            [
                ("10-recent-1", 10, "recent", 100 * 86400),
                ("10-recent-2", 10, "recent", 99 * 86400),
                ("10-prior", 10, "prior", 50 * 86400),
                ("20-recent", 20, "recent", 100 * 86400),
                ("20-prior", 20, "prior", 50 * 86400),
            ],
        )
        connection.commit()
        connection.close()
        return path

    def test_trend_explorer_uses_real_rows_filters_and_stable_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            intelligence = DeveloperIntelligence(self._database(Path(temp_dir)))
            first = intelligence.explore_trends(tag="co-op", limit=10)
            second = intelligence.explore_trends(tag="CO-OP", limit=10)

        self.assertEqual([item.steam_app_id for item in first], [item.steam_app_id for item in second])
        self.assertEqual([item.steam_app_id for item in first], [10, 20])
        self.assertTrue(all(0 <= item.score <= 100 for item in first))
        self.assertTrue(all(0 <= factor <= 1 for item in first for factor in item.factors.values()))
        self.assertTrue(first[0].explanation)
        self.assertNotIn("example", " ".join(first[0].explanation).lower())

    def test_market_opportunities_explain_demand_momentum_and_saturation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            opportunities = DeveloperIntelligence(self._database(Path(temp_dir))).tag_opportunities(limit=10)

        co_op = next(item for item in opportunities if item.value.casefold() == "co-op")
        self.assertEqual(co_op.matched_games, 2)
        self.assertEqual(co_op.total_games, 4)
        self.assertEqual(set(co_op.factors), {"demand", "momentum", "competition", "saturation"})
        self.assertTrue(any("2" in reason for reason in co_op.explanation))
        self.assertLessEqual(co_op.score, 100)

    def test_comparables_use_shared_tags_and_genres_and_are_bounded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            comparables = DeveloperIntelligence(self._database(Path(temp_dir))).comparable_games(10, limit=2)

        self.assertEqual([item.steam_app_id for item in comparables], [30, 20])
        self.assertEqual(comparables[0].shared_genres, ("Action",))
        self.assertEqual(comparables[0].shared_tags, ("RPG",))
        self.assertTrue(comparables[0].explanation)

    def test_empty_or_sparse_database_returns_empty_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "empty.sqlite3"
            sqlite3.connect(path).close()
            intelligence = DeveloperIntelligence(path)

            self.assertEqual(intelligence.explore_trends(), ())
            self.assertEqual(intelligence.genre_opportunities(), ())
            self.assertEqual(intelligence.comparable_games(10), ())

    def test_large_fixture_uses_bounded_sql_result_for_trends(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "large.sqlite3"
            connection = sqlite3.connect(path)
            connection.executescript(SCHEMA)
            connection.executemany(
                "INSERT INTO games (steam_app_id, name, owners_high, peak_ccu, total_reviews) VALUES (?, ?, ?, ?, ?)",
                [(index, f"Game {index:04d}", index * 10, index, index * 2) for index in range(1, 1201)],
            )
            connection.executemany(
                "INSERT INTO game_genres VALUES (?, ?)",
                [(index, "Action" if index % 2 else "Simulation") for index in range(1, 1201)],
            )
            connection.commit()
            connection.close()

            statements: list[str] = []
            real_connect = intelligence_module.connect_read_only

            def traced_connect(database_path):
                traced = real_connect(database_path)
                traced.set_trace_callback(statements.append)
                return traced

            with patch.object(intelligence_module, "connect_read_only", traced_connect):
                results = DeveloperIntelligence(path).explore_trends(genre="Action", limit=3)

        self.assertEqual(len(results), 3)
        self.assertTrue(any("LIMIT" in statement.upper() for statement in statements))


if __name__ == "__main__":
    unittest.main()

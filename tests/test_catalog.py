import sqlite3
import tempfile
import unittest
from pathlib import Path

from gamepulse.catalog import Catalog, GameSummary


class CatalogTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        path = root / "catalog.sqlite3"
        connection = sqlite3.connect(path)
        connection.executescript("""
            CREATE TABLE games (steam_app_id INTEGER PRIMARY KEY, name TEXT NOT NULL, release_date TEXT, price_usd REAL, owners_low INTEGER, owners_high INTEGER, peak_ccu INTEGER, total_reviews INTEGER, review_score REAL, header_image_url TEXT);
            CREATE TABLE game_tags (steam_app_id INTEGER, value TEXT);
            CREATE TABLE game_genres (steam_app_id INTEGER, value TEXT);
            CREATE TABLE review_summaries (steam_app_id INTEGER PRIMARY KEY, review_count INTEGER);
        """)
        connection.executemany("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            (10, "Alpha Quest", "2024-01-01", 10.0, 100, 200, 20, 100, 0.9, ""),
            (20, "Beta Builder", "2024-02-01", 0.0, None, None, 5, 0, None, ""),
            (30, "Gamma Action", "2024-03-01", 15.0, 100, 400, 25, 80, 0.85, ""),
        ])
        connection.execute("INSERT INTO game_tags VALUES (10, 'RPG')")
        connection.execute("INSERT INTO game_tags VALUES (10, 'FPS')")
        connection.execute("INSERT INTO game_tags VALUES (10, 'fps')")
        connection.execute("INSERT INTO game_genres VALUES (10, 'Role-Playing')")
        connection.execute("INSERT INTO game_genres VALUES (10, 'Action')")
        connection.execute("INSERT INTO game_genres VALUES (10, 'action')")
        connection.execute("INSERT INTO game_tags VALUES (30, 'RPG')")
        connection.execute("INSERT INTO game_genres VALUES (30, 'Role-Playing')")
        connection.execute("INSERT INTO review_summaries VALUES (10, 600)")
        connection.commit()
        connection.close()
        return path

    def test_search_returns_typed_matching_games(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = Catalog(self._database(Path(temp_dir)))
            results = catalog.search_games("alpha")

        self.assertEqual(results, [GameSummary(10, "Alpha Quest", "2024-01-01", 10.0, 100, 200, 20, 100, 0.9, ("FPS", "RPG", "fps"), ("Action", "Role-Playing", "action"), "")])

    def test_curated_ranking_requires_matched_review_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = Catalog(self._database(Path(temp_dir)))
            results = catalog.rank_demo_candidates()

        self.assertEqual(results[0].steam_app_id, 10)

    def test_preference_options_deduplicate_case_insensitively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = Catalog(self._database(Path(temp_dir)))
            options = catalog.preference_options(limit_per_group=20)

        self.assertEqual(tuple(item.casefold() for item in options.tags), ("fps", "rpg"))
        self.assertEqual(tuple(item.casefold() for item in options.genres), ("action", "role-playing"))

    def test_comparable_games_rank_by_shared_tags_and_genres(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = Catalog(self._database(Path(temp_dir)))
            results = catalog.comparable_games(10, limit=2)

        self.assertEqual([item.steam_app_id for item in results], [30])
        self.assertEqual(results[0].comparable_overlap, 3)


if __name__ == "__main__":
    unittest.main()

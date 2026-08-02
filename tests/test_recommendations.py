import sqlite3
import tempfile
import unittest
from pathlib import Path

from gamepulse.recommendations import PlayerPreferences, RecommendationEngine


class RecommendationTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        path = root / "recommendations.sqlite3"
        connection = sqlite3.connect(path)
        connection.executescript("""
            CREATE TABLE games (steam_app_id INTEGER PRIMARY KEY, name TEXT NOT NULL, release_date TEXT, price_usd REAL, owners_low INTEGER, owners_high INTEGER, peak_ccu INTEGER, total_reviews INTEGER, review_score REAL, header_image_url TEXT);
            CREATE TABLE game_tags (steam_app_id INTEGER, value TEXT);
            CREATE TABLE game_genres (steam_app_id INTEGER, value TEXT);
        """)
        connection.executemany("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            (10, "Seed RPG", "2024-01-01", 20.0, 100, 200, 20, 100, 0.9, ""),
            (20, "Similar RPG", "2024-02-01", 10.0, 100, 200, 10, 80, 0.95, ""),
            (30, "Hidden RPG", "2024-03-01", 5.0, 1, 2, 1, 5, 1.0, ""),
            (40, "Shooter", "2024-04-01", 10.0, 100, 200, 20, 90, 0.9, ""),
        ])
        connection.executemany("INSERT INTO game_tags VALUES (?, ?)", [(10, "Fantasy"), (20, "Fantasy"), (30, "Fantasy"), (40, "FPS")])
        connection.executemany("INSERT INTO game_genres VALUES (?, ?)", [(10, "Role-Playing"), (20, "Role-Playing"), (30, "Role-Playing"), (40, "Action")])
        connection.commit()
        connection.close()
        return path

    def test_similar_games_exclude_seed_and_owned_games(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = RecommendationEngine(self._database(Path(temp_dir)))
            results = engine.recommend_similar(10, PlayerPreferences(max_price_usd=15), excluded_app_ids={20})

        self.assertEqual([item.app_id for item in results], [30])
        self.assertTrue(results[0].reasons)

    def test_hidden_gem_preference_penalizes_high_popularity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._database(Path(temp_dir))
            connection = sqlite3.connect(path)
            connection.execute("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (50, "Popular RPG", "2024-05-01", 10.0, 10000000, 12000000, 1000, 5000, 0.95, ""))
            connection.execute("INSERT INTO game_tags VALUES (50, 'Fantasy')")
            connection.execute("INSERT INTO game_genres VALUES (50, 'Role-Playing')")
            connection.commit()
            connection.close()
            engine = RecommendationEngine(path)
            results = engine.recommend_similar(10, PlayerPreferences(discovery_mode="hidden_gems"), limit=10)

        self.assertNotIn(50, [item.app_id for item in results])
        self.assertEqual(results[0].app_id, 30)

    def test_match_scores_are_normalized_and_have_three_or_fewer_reasons(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = RecommendationEngine(self._database(Path(temp_dir)))
            results = engine.recommend_similar(10, PlayerPreferences(), limit=10)

        self.assertTrue(results)
        self.assertTrue(all(55 <= item.match_score <= 100 for item in results))
        self.assertTrue(all(1 <= len(item.reasons) <= 3 for item in results))
        self.assertTrue(all(item.score_band in {"Excellent match", "Strong match", "Worth exploring"} for item in results))

    def test_best_matches_can_include_a_popular_high_similarity_game(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._database(Path(temp_dir))
            connection = sqlite3.connect(path)
            connection.execute("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (50, "Popular RPG", "2024-05-01", 10.0, 10000000, 12000000, 1000, 5000, 0.95, ""))
            connection.execute("INSERT INTO game_tags VALUES (50, 'Fantasy')")
            connection.execute("INSERT INTO game_genres VALUES (50, 'Role-Playing')")
            connection.commit()
            connection.close()
            engine = RecommendationEngine(path)
            results = engine.recommend_similar(10, PlayerPreferences(discovery_mode="best_matches"), limit=10)

        self.assertIn(50, [item.app_id for item in results])

    def test_operating_system_filter_and_duplicate_names_are_respected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._database(Path(temp_dir))
            connection = sqlite3.connect(path)
            connection.execute("ALTER TABLE games ADD COLUMN windows INTEGER")
            connection.execute("ALTER TABLE games ADD COLUMN mac INTEGER")
            connection.execute("ALTER TABLE games ADD COLUMN linux INTEGER")
            connection.execute("UPDATE games SET windows = 1, mac = 0, linux = 0")
            connection.execute("UPDATE games SET linux = 1 WHERE steam_app_id = 30")
            connection.execute("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (50, "Similar RPG", "2024-05-01", 10.0, 100, 200, 10, 70, 0.95, "", 1, 0, 0))
            connection.execute("INSERT INTO game_tags VALUES (50, 'Fantasy')")
            connection.execute("INSERT INTO game_genres VALUES (50, 'Role-Playing')")
            connection.commit()
            connection.close()

            engine = RecommendationEngine(path)
            linux_results = engine.recommend_similar(10, PlayerPreferences(operating_system="Linux"), limit=10)
            connection = sqlite3.connect(path)
            connection.execute("UPDATE games SET linux = 1 WHERE steam_app_id = 50")
            connection.commit()
            connection.close()
            all_results = engine.recommend_similar(10, PlayerPreferences(), limit=10)

        self.assertEqual([item.app_id for item in linux_results], [30])
        names = [item.name.casefold() for item in all_results]
        self.assertEqual(len(names), len(set(names)))

    def test_ranker_can_return_more_than_fifty_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._database(Path(temp_dir))
            connection = sqlite3.connect(path)
            games = [
                (app_id, f"RPG Candidate {app_id}", "2024-01-01", 10.0, 100, 200, 10, 100, 0.9, "")
                for app_id in range(100, 220)
            ]
            connection.executemany("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", games)
            connection.executemany("INSERT INTO game_tags VALUES (?, 'Fantasy')", [(app_id,) for app_id, *_ in games])
            connection.executemany("INSERT INTO game_genres VALUES (?, 'Role-Playing')", [(app_id,) for app_id, *_ in games])
            connection.commit()
            connection.close()

            results = RecommendationEngine(path).recommend_similar(10, PlayerPreferences(), limit=100)

        self.assertEqual(len(results), 100)

    def test_broad_ranker_fills_window_with_catalogue_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._database(Path(temp_dir))
            connection = sqlite3.connect(path)
            games = [
                (app_id, f"Unrelated Candidate {app_id}", "2024-01-01", 10.0, 100, 200, 10, 100, 0.9, "")
                for app_id in range(100, 220)
            ]
            connection.executemany("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", games)
            connection.executemany("INSERT INTO game_tags VALUES (?, 'Strategy')", [(app_id,) for app_id, *_ in games])
            connection.executemany("INSERT INTO game_genres VALUES (?, 'Simulation')", [(app_id,) for app_id, *_ in games])
            connection.commit()
            connection.close()

            results = RecommendationEngine(path).recommend_similar(10, PlayerPreferences(), limit=100)

        self.assertEqual(len(results), 100)
        self.assertTrue(any("broader catalogue candidate" in item.reasons for item in results))


if __name__ == "__main__":
    unittest.main()

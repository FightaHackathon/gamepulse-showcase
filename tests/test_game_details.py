import sqlite3
import tempfile
import unittest
from pathlib import Path

from gamepulse.database import initialize_schema
from gamepulse.game_details import get_game_details


class GameDetailsTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        path = root / "game_details.sqlite3"
        connection = sqlite3.connect(path)
        initialize_schema(connection)
        connection.execute(
            "INSERT INTO games (steam_app_id, name, release_date, price_usd, total_reviews, review_score, header_image_url, short_description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (10, "Detail Quest", "2024-03-15", 19.99, 25, 0.84, "https://example.com/header.jpg", "A detailed quest."),
        )
        connection.execute(
            "INSERT INTO game_tags VALUES (?, ?)",
            (10, "Fantasy"),
        )
        connection.execute(
            "INSERT INTO game_genres VALUES (?, ?)",
            (10, "Role-Playing"),
        )
        connection.execute(
            "INSERT INTO review_summaries (steam_app_id, review_count, recommended_count, not_recommended_count, review_score, average_playtime_minutes) VALUES (?, ?, ?, ?, ?, ?)",
            (10, 25, 21, 4, 0.84, 123.5),
        )
        connection.executemany(
            "INSERT INTO reviews (review_id, steam_app_id, review_text, recommended, helpful_votes, funny_votes, created_at_unix, author_playtime_minutes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("new", 10, "The combat is excellent and the world is beautiful.", 1, 8, 1, 200, 180),
                ("old", 10, "The opening is slow, but the story improves.", 0, 2, 0, 100, 60),
                ("third", 10, "A smaller review that should be outside the requested page.", 1, 0, 0, 50, 20),
            ],
        )
        connection.commit()
        connection.close()
        return path

    def test_details_include_game_metadata_review_summary_and_catalogue_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            details = get_game_details(self._database(Path(temp_dir)), 10, review_limit=2)

        self.assertEqual(details.game.name, "Detail Quest")
        self.assertEqual(details.steam_store_url, "https://store.steampowered.com/app/10")
        self.assertEqual(details.game.tags, ("Fantasy",))
        self.assertEqual(details.review_catalogue.review_count, 25)
        self.assertEqual(details.review_catalogue.recommended_count, 21)
        self.assertEqual(details.review_catalogue.not_recommended_count, 4)
        self.assertEqual(details.review_catalogue.average_playtime_minutes, 123.5)
        self.assertEqual([review.review_id for review in details.review_catalogue.reviews], ["new", "old"])
        self.assertTrue(details.analysis.positive_themes)
        self.assertEqual(details.review_catalogue.reviews[0].author_playtime_minutes, 180)


if __name__ == "__main__":
    unittest.main()

import sqlite3
import tempfile
import unittest
from pathlib import Path

from gamepulse.review_analysis import analyze_reviews


class ReviewAnalysisTests(unittest.TestCase):
    def test_analysis_returns_sentiment_ratio_themes_and_excerpts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reviews.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE reviews (review_id TEXT, steam_app_id INTEGER, review_text TEXT, recommended INTEGER, created_at_unix INTEGER)")
            connection.executemany("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", [
                ("1", 10, "Great combat and beautiful world", 1, 1),
                ("2", 10, "The combat is repetitive and the bugs are frustrating", 0, 2),
            ])
            connection.commit()
            connection.close()

            result = analyze_reviews(path, 10)

        self.assertEqual(result.review_count, 2)
        self.assertEqual(result.positive_ratio, 0.5)
        self.assertTrue(result.positive_themes)
        self.assertTrue(result.negative_themes)
        self.assertEqual(len(result.excerpts), 2)


if __name__ == "__main__":
    unittest.main()

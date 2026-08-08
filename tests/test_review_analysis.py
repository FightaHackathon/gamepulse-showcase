import sqlite3
import tempfile
import unittest
from pathlib import Path

from gamepulse.review_analysis import ReviewPolarityBreakdown, ReviewTopic, analyze_reviews


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

    def test_keyword_topics_are_review_level_signals_with_polarity_denominators(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reviews.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE reviews (review_id TEXT, steam_app_id INTEGER, review_text TEXT, recommended INTEGER, created_at_unix INTEGER)")
            connection.executemany("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", [
                ("1", 10, "Combat is fun and the story is great", 1, 1),
                ("2", 10, "Combat is fun", 1, 2),
                ("3", 10, "Bugs and lag make combat frustrating", 0, 3),
                ("4", 10, "Bugs make the story frustrating", 0, 4),
            ])
            connection.commit()
            connection.close()

            result = analyze_reviews(path, 10)

        self.assertEqual(result.praise_topics[0], ReviewTopic("combat", 2, 2, 1.0))
        self.assertEqual(result.praise_topics[1], ReviewTopic("story", 1, 2, 0.5))
        complaint_topics = {topic.name: topic for topic in result.complaint_topics}
        self.assertEqual(complaint_topics["performance"], ReviewTopic("performance", 2, 2, 1.0))
        self.assertEqual(complaint_topics["bugs"], ReviewTopic("bugs", 2, 2, 1.0))
        self.assertEqual(complaint_topics["combat"], ReviewTopic("combat", 1, 2, 0.5))
        self.assertEqual(result.polarity_breakdown, ReviewPolarityBreakdown(2, 2, 0, 4, 0.5, 0.5, 0.0))

    def test_polarity_breakdown_keeps_unclassified_recommendations_in_denominator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reviews.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE reviews (review_id TEXT, steam_app_id INTEGER, review_text TEXT, recommended INTEGER, created_at_unix INTEGER)")
            connection.executemany("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", [
                ("1", 10, "Great combat", 1, 1),
                ("2", 10, "Bugs", 0, 2),
                ("3", 10, "An uncategorized review", None, 3),
            ])
            connection.commit()
            connection.close()

            result = analyze_reviews(path, 10)

        self.assertEqual(result.polarity_breakdown, ReviewPolarityBreakdown(1, 1, 1, 3, 0.3333, 0.3333, 0.3333))
        self.assertIn("bugs", {topic.name for topic in result.complaint_topics})
        self.assertNotIn("uncategorized", {topic.name for topic in result.complaint_topics})

    def test_topic_vocabulary_handles_requested_review_topics_and_coop_spelling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reviews.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE reviews (review_id TEXT, steam_app_id INTEGER, review_text TEXT, recommended INTEGER, created_at_unix INTEGER)")
            connection.executemany("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", [
                ("1", 10, "Great co-op gameplay and replayability", 1, 1),
                ("2", 10, "Bugs, poor balance, and monetization", 0, 2),
            ])
            connection.commit()
            connection.close()

            result = analyze_reviews(path, 10)

        praise = {topic.name for topic in result.praise_topics}
        complaints = {topic.name for topic in result.complaint_topics}
        self.assertTrue({"gameplay", "replayability", "multiplayer"}.issubset(praise))
        self.assertTrue({"bugs", "balance", "monetization"}.issubset(complaints))

    def test_empty_analysis_has_defaulted_intelligence_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reviews.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE reviews (review_id TEXT, steam_app_id INTEGER, review_text TEXT, recommended INTEGER, created_at_unix INTEGER)")
            connection.commit()
            connection.close()

            result = analyze_reviews(path, 10)

        self.assertEqual(result.praise_topics, ())
        self.assertEqual(result.complaint_topics, ())
        self.assertEqual(result.polarity_breakdown, ReviewPolarityBreakdown())


if __name__ == "__main__":
    unittest.main()

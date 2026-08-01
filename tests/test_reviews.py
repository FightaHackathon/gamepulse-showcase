import unittest

from gamepulse_data.reviews import normalise_review_row, summarise_reviews


class ReviewTests(unittest.TestCase):
    def test_normalise_review_row_drops_empty_text_and_creates_stable_id(self):
        self.assertIsNone(normalise_review_row({"appid": "10", "review": "  "}))
        review = normalise_review_row({"appid": "10", "review": "Great game", "voted_up": "True"})
        self.assertEqual(review["steam_app_id"], 10)
        self.assertTrue(review["review_id"])
        self.assertTrue(review["recommended"])

    def test_summarise_reviews_reconciles_counts(self):
        rows = [
            normalise_review_row({"appid": "10", "review": "Great game", "voted_up": "True", "word_count": "2"}),
            normalise_review_row({"appid": "10", "review": "Bad game", "voted_up": "False", "word_count": "2"}),
        ]
        summary = summarise_reviews(rows)[10]
        self.assertEqual(summary["review_count"], 2)
        self.assertEqual(summary["recommended_count"], 1)
        self.assertEqual(summary["review_score"], 0.5)

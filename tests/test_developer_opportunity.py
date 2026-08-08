import unittest

from gamepulse.forecasting import ForecastRange
from gamepulse.market_analysis import (
    MarketSnapshot,
    analyze_developer_opportunity,
)
from gamepulse.review_analysis import ReviewAnalysis


class DeveloperOpportunityTests(unittest.TestCase):
    def test_opportunity_score_is_bounded_and_explains_public_signals(self):
        snapshot = MarketSnapshot(
            10,
            seller_rank=4,
            owners_low=1000,
            owners_high=2000000,
            price_usd=20.0,
            total_reviews=10000,
            peak_ccu=5000,
            source_mode="Demo",
            source_name="fixture",
            observed_at="2026-08-01T00:00:00Z",
        )
        reviews = ReviewAnalysis(1000, 0.86, ("co-op",), ("grind",), ())
        forecast = ForecastRange(30, 80, 120, 160, "recent-activity baseline")

        opportunity = analyze_developer_opportunity(
            snapshot,
            reviews,
            forecast,
            creator_count=5,
            comparable_count=3,
            creator_scores=[40, 80],
        )

        self.assertGreaterEqual(opportunity.score, 0)
        self.assertLessEqual(opportunity.score, 100)
        self.assertIn(opportunity.score_band, {"Strong signal", "Promising signal", "Early signal"})
        self.assertEqual(len(opportunity.components), 5)
        self.assertEqual(opportunity.components.creator_fit, 0.6)
        self.assertTrue(any("public" in reason.lower() for reason in opportunity.reasons))
        self.assertIn("not verified", opportunity.disclaimer.lower())

    def test_missing_signals_do_not_crash_and_are_marked_in_reasons(self):
        snapshot = MarketSnapshot(
            10,
            seller_rank=None,
            owners_low=None,
            owners_high=None,
            price_usd=None,
            total_reviews=None,
            peak_ccu=None,
            source_mode="Local",
            source_name="fixture",
            observed_at="2026-08-01T00:00:00Z",
        )
        reviews = ReviewAnalysis(0, 0.0, (), (), ())
        forecast = ForecastRange(30, 0, 0, 0, "recent-activity baseline")

        opportunity = analyze_developer_opportunity(snapshot, reviews, forecast, creator_count=0, comparable_count=0)

        self.assertEqual(opportunity.score, 0)
        self.assertTrue(any("unavailable" in reason.lower() for reason in opportunity.reasons))


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from gamepulse.streamer_opportunity import (
    StreamerProfile,
    evaluate_snapshot_freshness,
    find_matching_opportunity,
    score_band,
    score_game_opportunities,
)
from gamepulse.providers.twitch import GameTrend, Snapshot


class StreamerOpportunityTests(unittest.TestCase):
    def test_balanced_demand_and_competition_beats_overcrowded_category(self):
        trends = [
            GameTrend("balanced", "Balanced", 10000, 100, 0.4),
            GameTrend("crowded", "Crowded", 50000, 5000, 0.4),
        ]

        results = score_game_opportunities(trends, StreamerProfile(preferred_tags=("FPS",)))

        self.assertEqual(results[0].game_id, "balanced")
        self.assertTrue(results[0].reasons)

    def test_opportunity_exposes_explainable_normalized_components(self):
        result = score_game_opportunities(
            [GameTrend("g1", "Example", 1000, 10, 0.5)],
            StreamerProfile(channel_size_tier="emerging"),
        )[0]

        self.assertGreater(result.score, 0.0)
        self.assertLessEqual(result.score, 1.0)
        self.assertEqual(result.score_band, "Promising opportunity")
        self.assertEqual(result.components.demand, 1.0)
        self.assertGreaterEqual(result.components.reach, 0.0)
        self.assertLessEqual(result.components.growth, 1.0)

    def test_snapshot_freshness_distinguishes_live_fresh_and_stale_data(self):
        now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)

        live = Snapshot("Live", "2026-08-01T12:00:00Z", "Twitch Helix", [])
        fresh = Snapshot("Demo", "2026-08-01T00:00:00Z", "fixture", [])
        stale = Snapshot("Demo", "2026-07-20T00:00:00Z", "fixture", [])

        self.assertEqual(evaluate_snapshot_freshness(live, now).status, "live")
        self.assertEqual(evaluate_snapshot_freshness(fresh, now).status, "fresh_snapshot")
        self.assertEqual(evaluate_snapshot_freshness(stale, now).status, "stale_snapshot")

    def test_score_band_has_stable_labels(self):
        self.assertEqual(score_band(0.8), "Strong opportunity")
        self.assertEqual(score_band(0.6), "Promising opportunity")
        self.assertEqual(score_band(0.2), "Competitive opportunity")

    def test_reach_strategy_and_channel_size_change_the_score(self):
        trends = [
            GameTrend("demand", "Demand", 10000, 1000, 0.2),
            GameTrend("reachable", "Reachable", 5000, 50, 0.2),
        ]

        balanced = score_game_opportunities(trends, StreamerProfile(strategy="balanced"))
        reach = score_game_opportunities(trends, StreamerProfile(strategy="reach"))
        emerging = score_game_opportunities(trends, StreamerProfile(channel_size_tier="emerging"))
        large = score_game_opportunities(trends, StreamerProfile(channel_size_tier="large"))

        self.assertNotEqual([(item.game_id, item.score) for item in balanced], [(item.game_id, item.score) for item in reach])
        self.assertNotEqual([(item.game_id, item.score) for item in emerging], [(item.game_id, item.score) for item in large])

    def test_preferred_tags_add_a_small_explainable_bonus(self):
        trend = GameTrend("g1", "Tagged", 1000, 10, 0.2, ("FPS",))

        without_preference = score_game_opportunities([trend], StreamerProfile())[0]
        with_preference = score_game_opportunities([trend], StreamerProfile(preferred_tags=("fps",)))[0]

        self.assertGreater(with_preference.score, without_preference.score)
        self.assertIn("matches your preferred category tags", with_preference.reasons)

    def test_selected_opportunity_matches_normalized_game_name(self):
        opportunity = SimpleNamespace(game_id="twitch-123", name="Counter-Strike")

        result = find_matching_opportunity([opportunity], "Counter Strike")

        self.assertIs(result, opportunity)


if __name__ == "__main__":
    unittest.main()

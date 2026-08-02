import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from gamepulse.streamer_opportunity import (
    HistoricalGameFeatures,
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
        self.assertLessEqual(result.score, 100.0)
        self.assertIn(result.score_band, {
            "Excellent opportunity", "Strong opportunity", "Promising opportunity",
            "Competitive category", "Weak evidence",
        })
        self.assertEqual(result.components.demand, 1.0)
        self.assertGreaterEqual(result.components.reach, 0.0)
        self.assertLessEqual(result.components.growth, 1.0)
        self.assertGreaterEqual(result.components.stability, 0.0)
        self.assertGreaterEqual(result.components.tier_suitability, 0.0)
        self.assertIn(result.trend_direction, {"Rising", "Stable", "Falling", "Unavailable"})
        self.assertGreaterEqual(result.confidence_score, 0.0)
        self.assertLessEqual(result.confidence_score, 1.0)

    def test_snapshot_freshness_distinguishes_live_fresh_and_stale_data(self):
        now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)

        live = Snapshot("Live", "2026-08-01T12:00:00Z", "Twitch Helix", [])
        fresh = Snapshot("Demo", "2026-08-01T00:00:00Z", "fixture", [])
        stale = Snapshot("Demo", "2026-07-20T00:00:00Z", "fixture", [])

        self.assertEqual(evaluate_snapshot_freshness(live, now).status, "live")
        self.assertEqual(evaluate_snapshot_freshness(fresh, now).status, "fresh_snapshot")
        self.assertEqual(evaluate_snapshot_freshness(stale, now).status, "stale_snapshot")

    def test_score_band_has_stable_labels(self):
        self.assertEqual(score_band(85), "Excellent opportunity")
        self.assertEqual(score_band(70), "Strong opportunity")
        self.assertEqual(score_band(55), "Promising opportunity")
        self.assertEqual(score_band(35), "Competitive category")
        self.assertEqual(score_band(10), "Weak evidence")

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
        self.assertIn("matches your genre, tag, or language preferences", with_preference.reasons)

    def test_selected_opportunity_matches_normalized_game_name(self):
        opportunity = SimpleNamespace(game_id="twitch-123", name="Counter-Strike")

        result = find_matching_opportunity([opportunity], "Counter Strike")

        self.assertIs(result, opportunity)

    def test_reachable_moderate_category_beats_extreme_overcrowding(self):
        trends = [
            GameTrend("huge", "Huge", 1_000_000, 100_000, 0.1),
            GameTrend("reachable", "Reachable", 30_000, 300, 0.45),
        ]

        results = score_game_opportunities(trends, StreamerProfile(strategy="balanced"))

        self.assertEqual(results[0].game_id, "reachable")

    def test_empty_category_does_not_rank_first(self):
        trends = [
            GameTrend("empty", "Empty", 0, 0, 0.0),
            GameTrend("active", "Active", 1_000, 20, 0.0),
        ]

        results = score_game_opportunities(trends, StreamerProfile())

        self.assertEqual(results[0].game_id, "active")
        self.assertEqual(results[-1].components.reachability, 0.0)

    def test_strategies_adjust_weights_explicitly(self):
        trends = [
            GameTrend("demand", "Demand", 200_000, 10_000, 0.1),
            GameTrend("growth", "Growth", 20_000, 100, 0.9),
            GameTrend("community", "Community", 8_000, 100, 0.5),
        ]

        balanced = score_game_opportunities(trends, StreamerProfile(strategy="balanced"))
        reach = score_game_opportunities(trends, StreamerProfile(strategy="reach"))
        growth = score_game_opportunities(trends, StreamerProfile(strategy="growth"))
        community = score_game_opportunities(trends, StreamerProfile(strategy="community"))

        self.assertNotEqual([item.score for item in balanced], [item.score for item in reach])
        self.assertNotEqual([item.score for item in balanced], [item.score for item in growth])
        self.assertNotEqual([item.score for item in balanced], [item.score for item in community])

    def test_historical_momentum_changes_component_and_trend_direction(self):
        trends = [
            GameTrend("rising", "Rising", 10_000, 100, 0.0),
            GameTrend("falling", "Falling", 10_000, 100, 0.0),
        ]
        history = {
            "rising": HistoricalGameFeatures(growth_score=0.8, observation_count=8),
            "falling": HistoricalGameFeatures(growth_score=-0.4, observation_count=8),
        }

        results = score_game_opportunities(trends, StreamerProfile(), historical_features=history)

        by_id = {item.game_id: item for item in results}
        rising, falling = by_id["rising"], by_id["falling"]
        self.assertGreater(rising.components.momentum, falling.components.momentum)
        self.assertEqual(rising.trend_direction, "Rising")
        self.assertEqual(falling.trend_direction, "Falling")

    def test_missing_momentum_is_cautious_and_reweighted(self):
        trend = GameTrend("g1", "No History", 10_000, 100, 0.0)

        result = score_game_opportunities([trend], StreamerProfile())[0]

        self.assertEqual(result.trend_direction, "Unavailable")
        self.assertTrue(any("momentum" in caution.lower() for caution in result.cautions))
        self.assertGreater(result.score, 0.0)
        self.assertLessEqual(result.score, 100.0)

    def test_verified_steam_and_twitch_preferences_contribute_to_fit(self):
        trend = GameTrend("g1", "Mapped", 10_000, 100, 0.2, ("Cozy",), language_distribution=(("en", 10),))
        profile = StreamerProfile(
            preferred_genres=("Simulation",),
            preferred_steam_tags=("Farming",),
            preferred_twitch_tags=("Cozy",),
            preferred_languages=("en",),
        )

        result = score_game_opportunities(
            [trend],
            profile,
            verified_steam_mappings={"g1": SimpleNamespace(steam_app_id=42, is_reliable=True)},
            steam_features={42: {"genres": ("Simulation",), "tags": ("Farming",)}},
            source_mode="Live",
            observed_at="2026-08-01T12:00:00Z",
        )[0]

        self.assertGreater(result.components.preference_fit, 0.0)
        self.assertIn("preference", " ".join(result.reasons).lower())
        self.assertEqual(result.steam_app_id, 42)
        self.assertEqual(result.source_mode, "Live")
        self.assertEqual(result.observed_at, "2026-08-01T12:00:00Z")

    def test_tier_suitability_changes_for_realistic_category_ranges(self):
        trends = [
            GameTrend("emerging", "Emerging", 8_000, 120, 0.2),
            GameTrend("large", "Large", 150_000, 4_000, 0.2),
        ]

        emerging = score_game_opportunities(trends, StreamerProfile(channel_size_tier="emerging"))
        large = score_game_opportunities(trends, StreamerProfile(channel_size_tier="large"))
        emerging_components = {item.game_id: item.components.tier_suitability for item in emerging}
        large_components = {item.game_id: item.components.tier_suitability for item in large}

        self.assertGreater(emerging_components["emerging"], emerging_components["large"])
        self.assertGreater(large_components["large"], large_components["emerging"])

    def test_concentration_and_quality_cautions_are_explicit(self):
        trend = GameTrend(
            "g1", "Concentrated", 10_000, 100, -0.2,
            top_one_viewer_share=0.65,
            top_five_viewer_share=0.95,
            contributing_stream_rows=2,
            partial_coverage=True,
        )

        result = score_game_opportunities(
            [trend],
            StreamerProfile(),
            source_mode="Demo",
            observed_at="2020-01-01T00:00:00Z",
            now=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )[0]
        cautions = " ".join(result.cautions).lower()

        self.assertIn("concentration", cautions)
        self.assertIn("limited", cautions)
        self.assertIn("stale", cautions)
        self.assertIn("falling", cautions)
        self.assertIn("demo", cautions)
        self.assertIn("mapping", cautions)

    def test_confidence_is_independent_from_opportunity_score(self):
        trend = GameTrend("g1", "Same Signals", 10_000, 100, 0.5, contributing_stream_rows=20)
        history = {"g1": HistoricalGameFeatures(growth_score=0.5, observation_count=10, observation_consistency=1.0)}

        live = score_game_opportunities(
            [trend], StreamerProfile(), historical_features=history,
            source_mode="Live", observed_at="2026-08-01T12:00:00Z",
            now=datetime(2026, 8, 1, 13, tzinfo=timezone.utc),
        )[0]
        demo = score_game_opportunities(
            [trend], StreamerProfile(), historical_features=history,
            source_mode="Demo", observed_at="2020-01-01T00:00:00Z",
            now=datetime(2026, 8, 1, 13, tzinfo=timezone.utc),
        )[0]

        self.assertEqual(live.score, demo.score)
        self.assertGreater(live.confidence_score, demo.confidence_score)

    def test_ties_use_name_then_game_id_for_deterministic_sorting(self):
        trends = [
            GameTrend("2", "Same", 1_000, 20, 0.5),
            GameTrend("1", "Same", 1_000, 20, 0.5),
        ]

        results = score_game_opportunities(trends, StreamerProfile())

        self.assertEqual([item.game_id for item in results], ["1", "2"])

    def test_all_component_values_and_scores_are_bounded(self):
        trends = [
            GameTrend("empty", "Empty", 0, 0, -1.0),
            GameTrend("active", "Active", 100_000, 1_000, 1.0),
        ]

        results = score_game_opportunities(trends, StreamerProfile(strategy="community"))

        for result in results:
            self.assertGreaterEqual(result.score, 0.0)
            self.assertLessEqual(result.score, 100.0)
            for value in (
                result.components.demand, result.components.reachability, result.components.momentum,
                result.components.competition, result.components.stability,
                result.components.preference_fit, result.components.tier_suitability,
            ):
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)


if __name__ == "__main__":
    unittest.main()

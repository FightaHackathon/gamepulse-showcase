import math
import unittest

from gamepulse.developer_prediction import DeveloperPredictionInput, predict_developer_outcome


class DeveloperPredictionTests(unittest.TestCase):
    def test_valid_owner_range_produces_explicit_gross_and_net_scenarios(self):
        result = predict_developer_outcome(
            DeveloperPredictionInput(
                steamspy_owners_low=100,
                steamspy_owners_high=200,
                selected_game_price_usd=20.0,
            )
        )

        self.assertEqual(result.estimated_owner_units, (100, 200))
        self.assertEqual(result.scenario_gross_usd, (1400.0, 2800.0))
        self.assertEqual(result.scenario_net_usd, (980.0, 1960.0))
        self.assertIn("estimated owner units", " ".join(result.assumptions).lower())
        self.assertIn("scenario", result.source_caveat.lower())
        self.assertIn("not actual", result.source_caveat.lower())
        self.assertEqual(result.realized_price_fraction, 0.70)
        self.assertEqual(result.platform_fee_rate, 0.30)

    def test_missing_owner_range_keeps_revenue_unavailable(self):
        result = predict_developer_outcome(
            DeveloperPredictionInput(selected_game_price_usd=20.0)
        )

        self.assertIsNone(result.estimated_owner_units)
        self.assertIsNone(result.scenario_gross_usd)
        self.assertIsNone(result.scenario_net_usd)
        self.assertIn("owner", result.source_caveat.lower())

    def test_missing_or_invalid_price_keeps_revenue_unavailable(self):
        for price in (None, -1.0, math.inf, "bad"):
            with self.subTest(price=price):
                result = predict_developer_outcome(
                    DeveloperPredictionInput(
                        steamspy_owners_low=100,
                        steamspy_owners_high=200,
                        selected_game_price_usd=price,
                    )
                )
                self.assertEqual(result.estimated_owner_units, (100, 200))
                self.assertIsNone(result.scenario_gross_usd)
                self.assertIsNone(result.scenario_net_usd)

    def test_custom_assumptions_are_applied_and_exposed(self):
        result = predict_developer_outcome(
            DeveloperPredictionInput(
                steamspy_owners_low=100,
                steamspy_owners_high=200,
                selected_game_price_usd=20.0,
                realized_price_fraction=0.5,
                platform_fee_rate=0.1,
            )
        )

        self.assertEqual(result.scenario_gross_usd, (1000.0, 2000.0))
        self.assertEqual(result.scenario_net_usd, (900.0, 1800.0))
        self.assertIn("50.0%", " ".join(result.assumptions))
        self.assertIn("10.0%", " ".join(result.assumptions))

    def test_all_competition_factors_use_locked_weights(self):
        result = predict_developer_outcome(
            DeveloperPredictionInput(
                twitch_channel_count=50,
                twitch_channel_peer_max=100,
                review_count=50,
                review_peer_max=100,
                comparable_game_count=10,
                comparable_game_peer_max=20,
            )
        )

        self.assertEqual(result.competition_index, 50.0)
        self.assertIn("channel", result.competition_explanation.lower())
        self.assertIn("comparable", result.competition_explanation.lower())
        self.assertIn("review", result.competition_explanation.lower())
        self.assertNotIn("viewer", result.competition_explanation.lower())

    def test_partial_competition_factors_are_renormalized(self):
        result = predict_developer_outcome(
            DeveloperPredictionInput(
                twitch_channel_count=50,
                twitch_channel_peer_max=100,
                review_count=50,
                review_peer_max=100,
            )
        )

        self.assertEqual(result.competition_index, 50.0)
        self.assertIn("comparable", result.competition_explanation.lower())
        self.assertIn("excluded", result.competition_explanation.lower())

    def test_no_competition_factors_returns_none_instead_of_zero(self):
        result = predict_developer_outcome(DeveloperPredictionInput())

        self.assertIsNone(result.competition_index)
        self.assertIn("unavailable", result.competition_explanation.lower())

    def test_malformed_values_are_bounded_or_unavailable(self):
        result = predict_developer_outcome(
            DeveloperPredictionInput(
                steamspy_owners_low=-10,
                steamspy_owners_high=math.inf,
                selected_game_price_usd=20.0,
                realized_price_fraction=2.0,
                platform_fee_rate=-1.0,
                twitch_channel_count=200,
                twitch_channel_peer_max=100,
                comparable_game_count=-1,
                comparable_game_peer_max=10,
            )
        )

        self.assertIsNone(result.estimated_owner_units)
        self.assertIsNone(result.scenario_gross_usd)
        self.assertIsNone(result.scenario_net_usd)
        self.assertEqual(result.realized_price_fraction, 1.0)
        self.assertEqual(result.platform_fee_rate, 0.0)
        self.assertEqual(result.competition_index, 100.0)

    def test_owner_bounds_are_normalized(self):
        result = predict_developer_outcome(
            DeveloperPredictionInput(
                steamspy_owners_low=200,
                steamspy_owners_high=100,
                selected_game_price_usd=10.0,
            )
        )

        self.assertEqual(result.estimated_owner_units, (100, 200))
        self.assertEqual(result.scenario_gross_usd, (700.0, 1400.0))

    def test_overflowing_scenario_is_unavailable(self):
        result = predict_developer_outcome(
            DeveloperPredictionInput(
                steamspy_owners_low=1e308,
                steamspy_owners_high=1e308,
                selected_game_price_usd=1e308,
            )
        )

        self.assertEqual(result.estimated_owner_units, (int(1e308), int(1e308)))
        self.assertIsNone(result.scenario_gross_usd)
        self.assertIsNone(result.scenario_net_usd)


if __name__ == "__main__":
    unittest.main()

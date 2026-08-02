import unittest
from types import SimpleNamespace

from gamepulse.growth_windows import calculate_window_growth
from gamepulse.providers.twitch import GameTrend
from gamepulse.streamer_opportunity import StreamerProfile, score_game_opportunities
from gamepulse.ui.developer import _profile_from_records
from gamepulse.ui.streamer import _historical_features
from gamepulse.ui.streamer_components import render_category_deep_dive


def _row(timestamp: str, viewers: object) -> dict[str, object]:
    return {"observed_at": timestamp, "viewer_count": viewers}


def _creator_row(timestamp: str, viewers: int) -> dict[str, object]:
    return {
        "observed_at": timestamp,
        "stream_id": f"stream-{timestamp}",
        "streamer_id": "creator-1",
        "streamer_name": "Creator One",
        "streamer_login": "creator_one",
        "game_id": "target",
        "game_name": "Target Game",
        "viewer_count": viewers,
        "language": "en",
        "tags": (),
        "channel_size_tier": "unknown",
        "source_mode": "Live",
        "source_name": "Twitch",
    }


class _FakeStreamlit:
    def __init__(self):
        self.markdowns = []
        self.infos = []
        self.plotly_figures = []

    def markdown(self, value, **_kwargs):
        self.markdowns.append(value)

    def info(self, value):
        self.infos.append(value)

    def plotly_chart(self, figure, **_kwargs):
        self.plotly_figures.append(figure)


class GrowthWindowTests(unittest.TestCase):
    latest = "2026-08-10T12:00:00Z"

    def test_one_day_baseline_returns_change_and_metadata(self):
        result = calculate_window_growth(
            [
                _row("2026-08-09T12:00:00Z", 100),
                _row(self.latest, 125),
            ],
            "one-day",
        )

        self.assertTrue(result.available)
        self.assertAlmostEqual(result.percentage_change, 0.25)
        self.assertEqual(result.actual_interval_hours, 24.0)
        self.assertEqual(result.baseline_timestamp, "2026-08-09T12:00:00Z")
        self.assertEqual(result.latest_timestamp, self.latest)

    def test_seven_day_baseline_is_selected_within_documented_window(self):
        result = calculate_window_growth(
            [
                _row("2026-08-03T12:00:00Z", 100),
                _row(self.latest, 150),
            ],
            "seven-day",
        )

        self.assertTrue(result.available)
        self.assertAlmostEqual(result.percentage_change, 0.50)
        self.assertEqual(result.actual_interval_hours, 168.0)

    def test_window_tolerance_boundaries_are_inclusive(self):
        one_day_low = calculate_window_growth(
            [_row("2026-08-09T18:00:00Z", 100), _row(self.latest, 110)],
            "one-day",
        )
        one_day_high = calculate_window_growth(
            [_row("2026-08-09T06:00:00Z", 100), _row(self.latest, 110)],
            "one-day",
        )
        seven_day_low = calculate_window_growth(
            [_row("2026-08-04T12:00:00Z", 100), _row(self.latest, 110)],
            "seven-day",
        )
        seven_day_high = calculate_window_growth(
            [_row("2026-08-02T12:00:00Z", 100), _row(self.latest, 110)],
            "seven-day",
        )

        self.assertTrue(all(result.available for result in (one_day_low, one_day_high, seven_day_low, seven_day_high)))

    def test_two_hour_history_is_unavailable(self):
        result = calculate_window_growth(
            [_row("2026-08-10T10:00:00Z", 100), _row(self.latest, 125)],
            "one-day",
        )

        self.assertFalse(result.available)
        self.assertIsNone(result.percentage_change)
        self.assertEqual(result.latest_timestamp, self.latest)

    def test_twenty_day_baseline_is_not_used_for_seven_day_growth(self):
        result = calculate_window_growth(
            [_row("2026-07-21T12:00:00Z", 100), _row(self.latest, 125)],
            "seven-day",
        )

        self.assertFalse(result.available)
        self.assertIsNone(result.baseline_timestamp)

    def test_closest_valid_candidate_is_selected(self):
        result = calculate_window_growth(
            [
                _row("2026-08-09T16:00:00Z", 100),
                _row("2026-08-09T13:00:00Z", 80),
                _row(self.latest, 120),
            ],
            "one-day",
        )

        self.assertEqual(result.baseline_timestamp, "2026-08-09T13:00:00Z")
        self.assertEqual(result.actual_interval_hours, 23.0)

    def test_zero_negative_and_malformed_baselines_are_unavailable(self):
        result = calculate_window_growth(
            [
                _row("2026-08-09T12:00:00Z", 0),
                _row("2026-08-09T11:00:00Z", -10),
                _row("2026-08-09T10:00:00Z", "not-a-number"),
                _row(self.latest, 125),
            ],
            "one-day",
        )

        self.assertFalse(result.available)
        self.assertIsNone(result.percentage_change)

    def test_developer_profile_only_accepts_a_seven_day_baseline(self):
        profile = _profile_from_records(
            "creator-1",
            [
                _creator_row("2026-08-03T12:00:00Z", 100),
                _creator_row(self.latest, 150),
            ],
            "Target Game",
            (),
        )

        self.assertAlmostEqual(profile.seven_day_growth, 0.5)
        self.assertEqual(profile.seven_day_growth_baseline_at, "2026-08-03T12:00:00Z")
        self.assertEqual(profile.seven_day_growth_latest_at, self.latest)
        self.assertEqual(profile.seven_day_growth_interval_hours, 168.0)

    def test_developer_profile_does_not_label_a_twenty_day_comparison_seven_day(self):
        profile = _profile_from_records(
            "creator-1",
            [
                _creator_row("2026-07-21T12:00:00Z", 100),
                _creator_row(self.latest, 150),
            ],
            "Target Game",
            (),
        )

        self.assertIsNone(profile.seven_day_growth)

    def test_streamer_historical_features_do_not_use_unwindowed_growth_score(self):
        features = _historical_features(
            (
                {"observed_at": "2026-07-21T12:00:00Z", "viewer_count": 100, "growth_score": 0.75},
                {"observed_at": self.latest, "viewer_count": 150, "growth_score": 0.75},
            )
        )

        self.assertIsNotNone(features)
        self.assertIsNone(features.growth_score)

    def test_streamer_momentum_uses_the_shared_seven_day_comparison(self):
        features = _historical_features(
            (
                {"observed_at": "2026-08-03T12:00:00Z", "viewer_count": 100, "growth_score": 0.75},
                {"observed_at": self.latest, "viewer_count": 150, "growth_score": 0.75},
            )
        )

        result = score_game_opportunities(
            [GameTrend("g1", "Example", 150, 10, 0.0)],
            StreamerProfile(),
            historical_features={"g1": features},
        )[0]

        self.assertAlmostEqual(features.growth_score, 0.5)
        self.assertEqual(features.growth_comparison.baseline_timestamp, "2026-08-03T12:00:00Z")
        self.assertEqual(result.trend_direction, "Rising")
        self.assertEqual(result.components.momentum, 0.5)

    def test_streamer_deep_dive_labels_missing_baseline_as_insufficient_history(self):
        st = _FakeStreamlit()
        trend = SimpleNamespace(
            name="Example",
            viewer_count=125,
            channel_count=10,
            viewer_to_channel=12.5,
            top_one_viewer_share=0.0,
            top_five_viewer_share=0.0,
            language_distribution={},
            partial_coverage=False,
        )

        render_category_deep_dive(
            st,
            trend,
            history=(_row("2026-08-10T10:00:00Z", 100), _row(self.latest, 125)),
        )

        output = "\n".join(st.markdowns + st.infos)
        self.assertIn("Unavailable - insufficient history", output)


if __name__ == "__main__":
    unittest.main()

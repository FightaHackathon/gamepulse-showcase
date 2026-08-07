import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from gamepulse.providers.contracts import GameSignal, SignalSnapshot
from gamepulse.providers.twitch import GameTrend
from gamepulse.streamer_opportunity import (
    StreamerProfile,
    audience_metric_label,
    evaluate_snapshot_freshness,
    find_matching_opportunity,
    renormalized_weighted_score,
    score_band,
    score_game_opportunities,
)


def signal(
    game_id: str,
    name: str,
    *,
    audience: float | None = 1000,
    audience_metric: str | None = "steam_current_players",
    competition: float | None = None,
    competition_metric: str | None = None,
    growth: float | None = 0.5,
    tags: tuple[str, ...] = (),
    sentiment: float | None = 0.8,
) -> GameSignal:
    return GameSignal(
        game_id=game_id,
        name=name,
        audience_value=audience,
        audience_metric=audience_metric,
        competition_value=competition,
        competition_metric=competition_metric,
        growth_score=growth,
        tags=tags,
        genres=(),
        platform="Steam" if str(audience_metric or "").startswith("steam") else "Twitch",
        source_name="test source",
        observed_at="2026-08-07T00:00:00Z",
        confidence="test",
        source_mode="Prepared",
        sentiment_score=sentiment,
    )


class StreamerOpportunityTests(unittest.TestCase):
    def test_missing_competition_is_excluded_not_treated_as_zero_competition(self):
        unknown = signal("unknown", "Unknown competition", competition=None, competition_metric=None)
        observed_zero = signal("zero", "Observed zero", competition=0, competition_metric="twitch_live_channels")

        results = {item.game_id: item for item in score_game_opportunities([unknown, observed_zero], StreamerProfile())}

        self.assertIsNone(results["unknown"].components.competition)
        self.assertIn("competition", results["unknown"].unavailable_components)
        self.assertIn("excluded from scoring", " ".join(results["unknown"].reasons))
        self.assertLessEqual(results["unknown"].score, results["zero"].score)

    def test_unavailable_component_weights_are_renormalized(self):
        result = renormalized_weighted_score(
            {"audience": 0.8, "competition": None},
            {"audience": 0.5, "competition": 0.5},
        )

        self.assertAlmostEqual(result, 0.8)

    def test_higher_legitimate_growth_increases_opportunity_score(self):
        low = signal("low", "Low growth", growth=0.2)
        high = signal("high", "High growth", growth=0.9)

        results = {item.game_id: item for item in score_game_opportunities([low, high], StreamerProfile())}

        self.assertGreater(results["high"].score, results["low"].score)

    def test_preference_tag_overlap_affects_score_and_reason(self):
        tagged = signal("tagged", "Tagged", tags=("FPS",))
        plain = signal("plain", "Plain", tags=("Puzzle",))

        results = {item.game_id: item for item in score_game_opportunities([tagged, plain], StreamerProfile(preferred_tags=("fps",)))}

        self.assertGreater(results["tagged"].score, results["plain"].score)
        self.assertIn("Matches your preferred genre/tag signals", results["tagged"].reasons)

    def test_results_are_deterministic(self):
        trends = [
            signal("a", "Alpha", audience=5000, growth=0.6),
            signal("b", "Beta", audience=3000, growth=0.7),
        ]
        profile = StreamerProfile(strategy="growth", channel_size_tier="mid-size")

        first = score_game_opportunities(trends, profile)
        second = score_game_opportunities(trends, profile)

        self.assertEqual(first, second)

    def test_snapshot_freshness_supports_live_prepared_fresh_and_stale(self):
        now = datetime(2026, 8, 7, 12, tzinfo=timezone.utc)
        live = SignalSnapshot("Live", "2026-08-07T12:00:00Z", "provider", [])
        prepared = SignalSnapshot("Prepared", "2026-08-01T00:00:00Z", "database", [])
        fresh = SignalSnapshot("Imported", "2026-08-07T00:00:00Z", "snapshot", [])
        stale = SignalSnapshot("Imported", "2026-07-20T00:00:00Z", "snapshot", [])

        self.assertEqual(evaluate_snapshot_freshness(live, now).status, "live")
        self.assertEqual(evaluate_snapshot_freshness(prepared, now).status, "prepared")
        self.assertEqual(evaluate_snapshot_freshness(fresh, now).status, "fresh_snapshot")
        self.assertEqual(evaluate_snapshot_freshness(stale, now).status, "stale_snapshot")

    def test_steam_player_metric_is_never_labelled_twitch_viewers(self):
        self.assertEqual(audience_metric_label("steam_current_players"), "current Steam players")
        self.assertNotIn("Twitch", audience_metric_label("steam_current_players"))
        self.assertEqual(audience_metric_label("twitch_viewers"), "observed Twitch viewers")

    def test_legacy_twitch_game_trend_still_scores(self):
        result = score_game_opportunities([GameTrend("g1", "Example", 1000, 10, 0.5)], StreamerProfile())[0]

        self.assertEqual(result.audience_metric, "twitch_viewers")
        self.assertEqual(result.competition_metric, "twitch_live_channels")
        self.assertEqual(result.viewer_count, 1000)

    def test_score_band_has_stable_labels(self):
        self.assertEqual(score_band(0.8), "Strong opportunity")
        self.assertEqual(score_band(0.6), "Promising opportunity")
        self.assertEqual(score_band(0.2), "Competitive opportunity")

    def test_selected_opportunity_matches_normalized_game_name(self):
        opportunity = SimpleNamespace(game_id="source-123", name="Counter-Strike")

        result = find_matching_opportunity([opportunity], "Counter Strike")

        self.assertIs(result, opportunity)


if __name__ == "__main__":
    unittest.main()

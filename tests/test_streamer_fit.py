import unittest

from gamepulse.providers.contracts import CreatorSignal
from gamepulse.streamer_fit import StreamerProfile, rank_creators, rank_streamers


class StreamerFitTests(unittest.TestCase):
    def test_legacy_genre_match_still_drives_fit(self):
        game = {"genres": {"action"}, "tags": {"fps"}, "language": "en"}
        streamers = [
            StreamerProfile("match", {"action", "fps"}, "en", "emerging", 500),
            StreamerProfile("mismatch", {"rpg"}, "en", "large", 5000),
        ]

        results = rank_streamers(game, streamers)

        self.assertEqual(results[0].streamer_id, "match")
        self.assertTrue(results[0].reasons)

    def test_source_neutral_creator_history_tags_and_provenance_are_exposed(self):
        game = {"name": "Example Game", "genres": {"action"}, "tags": {"fps"}, "language": "en"}
        creator = CreatorSignal(
            creator_id="creator-1",
            name="Example Creator",
            platform="YouTube",
            profile_url="https://example.invalid/creator",
            game_id=None,
            game_name=None,
            audience_value=300,
            audience_metric="avg_viewers",
            language="en",
            channel_size_tier="emerging",
            tags=("FPS", "Action"),
            games=("Example Game",),
            observed_at="2026-08-07T00:00:00Z",
            source_name="creator directory",
            confidence="creator_submitted",
            source_mode="Creator submitted",
        )

        result = rank_creators(game, [creator], tier="emerging", language="en")[0]

        self.assertGreaterEqual(result.score, 75)
        self.assertEqual(result.creator_name, "Example Creator")
        self.assertEqual(result.platform, "YouTube")
        self.assertEqual(result.source_mode, "Creator submitted")
        self.assertIn("creator directory", " ".join(result.reasons))

    def test_missing_audience_is_excluded_instead_of_fabricated(self):
        game = {"name": "Example Game", "genres": {"indie"}, "tags": set()}
        creator = CreatorSignal(
            creator_id="creator-2",
            name="No Audience Creator",
            platform="Manual",
            profile_url=None,
            game_id=None,
            game_name=None,
            audience_value=None,
            audience_metric=None,
            language="",
            channel_size_tier="unknown",
            tags=("indie",),
            games=("Example Game",),
            observed_at="2026-08-07T00:00:00Z",
            source_name="manual directory",
            confidence="manual",
            source_mode="Manual",
        )

        result = rank_creators(game, [creator])[0]

        self.assertIn("audience size is unavailable", " ".join(result.reasons))
        self.assertIsNone(result.audience_value)

    def test_fit_score_is_bounded_and_has_a_human_band(self):
        game = {"genres": {"action"}, "tags": {"fps"}, "language": "en"}
        results = rank_streamers(game, [StreamerProfile("match", {"action", "fps"}, "en", "emerging", 500)])

        self.assertGreaterEqual(results[0].score, 0)
        self.assertLessEqual(results[0].score, 100)
        self.assertIn(results[0].score_band, {"Strong fit", "Promising fit", "Low fit"})


if __name__ == "__main__":
    unittest.main()

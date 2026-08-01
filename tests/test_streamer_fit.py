import unittest

from gamepulse.streamer_fit import StreamerProfile, rank_streamers


class StreamerFitTests(unittest.TestCase):
    def test_genre_match_and_channel_tier_drive_fit(self):
        game = {"genres": {"action"}, "tags": {"fps"}, "language": "en"}
        streamers = [
            StreamerProfile("match", {"action", "fps"}, "en", "emerging", 500),
            StreamerProfile("mismatch", {"rpg"}, "en", "large", 5000),
        ]

        results = rank_streamers(game, streamers)

        self.assertEqual(results[0].streamer_id, "match")
        self.assertTrue(results[0].reasons)

    def test_fit_score_is_bounded_and_has_a_human_band(self):
        game = {"genres": {"action"}, "tags": {"fps"}, "language": "en"}
        results = rank_streamers(game, [StreamerProfile("match", {"action", "fps"}, "en", "emerging", 500)])

        self.assertGreaterEqual(results[0].score, 0)
        self.assertLessEqual(results[0].score, 100)
        self.assertIn(results[0].score_band, {"Strong fit", "Promising fit", "Low fit"})


if __name__ == "__main__":
    unittest.main()

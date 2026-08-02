import unittest

from gamepulse.streamer_fit import PromotionCampaignProfile, StreamerProfile, rank_streamers


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

    def test_exact_game_category_is_a_developer_fit_signal(self):
        game = {"name": "Counter-Strike", "genres": {"action"}, "tags": {"fps"}, "language": "en"}
        streamers = [
            StreamerProfile("z-exact", {"Counter-Strike", "action", "fps"}, "en", "emerging", 500),
            StreamerProfile("a-generic", {"action", "fps"}, "en", "emerging", 500),
        ]

        results = rank_streamers(game, streamers)

        self.assertEqual(results[0].streamer_id, "z-exact")
        self.assertGreater(results[0].score, results[1].score)
        self.assertIn("matches Counter-Strike category", results[0].reasons)

    def test_category_history_match_uses_aggregate_history(self):
        campaign = PromotionCampaignProfile("New RPG", genres=("rpg",))
        streamers = [
            StreamerProfile(
                "history-match", {"fps"}, "en", "emerging", 2_000,
                category_history=("RPG",), median_viewers=1_800, peak_viewers=4_000,
                primary_category="FPS", primary_category_share=0.5, viewer_volatility=0.2,
                observation_count=10, source_mode="Live",
            ),
            StreamerProfile(
                "current-only", {"RPG"}, "en", "emerging", 2_000,
                median_viewers=1_800, peak_viewers=4_000,
                primary_category="RPG", primary_category_share=1.0, viewer_volatility=0.2,
                observation_count=10, source_mode="Live",
            ),
        ]

        results = rank_streamers(campaign, streamers)
        by_id = {item.streamer_id: item for item in results}

        self.assertGreater(by_id["history-match"].components.category_history_fit, 0.0)
        self.assertEqual(by_id["history-match"].primary_category, "FPS")

    def test_similar_game_history_match_is_a_distinct_component(self):
        campaign = PromotionCampaignProfile("New Game", similar_games=("Stardew Valley",))
        streamers = [
            StreamerProfile(
                "similar", {"variety"}, "en", "mid-size", 3_000,
                category_history=("Stardew Valley",), similar_game_history=("Stardew Valley",),
                median_viewers=2_500, peak_viewers=6_000, observation_count=8,
            ),
            StreamerProfile(
                "other", {"variety"}, "en", "mid-size", 3_000,
                category_history=("Other Game",), median_viewers=2_500,
                peak_viewers=6_000, observation_count=8,
            ),
        ]

        results = rank_streamers(campaign, streamers)
        by_id = {item.streamer_id: item for item in results}

        self.assertEqual(results[0].streamer_id, "similar")
        self.assertGreater(by_id["similar"].components.similar_game_fit, by_id["other"].components.similar_game_fit)
        self.assertEqual(by_id["similar"].similar_game_matches, ("Stardew Valley",))
        self.assertEqual(by_id["other"].similar_game_matches, ())

    def test_fit_exposes_direct_selected_game_history_separately(self):
        campaign = PromotionCampaignProfile("New Game", similar_games=("Stardew Valley",))
        streamers = [
            StreamerProfile(
                "direct", {"variety"}, "en", "mid-size", 3_000,
                category_history=("New Game",), median_viewers=2_500,
                peak_viewers=6_000, observation_count=8,
            ),
            StreamerProfile(
                "similar", {"variety"}, "en", "mid-size", 3_000,
                category_history=("Stardew Valley",), similar_game_history=("Stardew Valley",),
                median_viewers=2_500, peak_viewers=6_000, observation_count=8,
            ),
        ]

        fits = {item.streamer_id: item for item in rank_streamers(campaign, streamers)}

        self.assertEqual(fits["direct"].direct_game_matches, ("New Game",))
        self.assertEqual(fits["similar"].direct_game_matches, ())
        self.assertEqual(fits["similar"].similar_game_matches, ("Stardew Valley",))

    def test_large_creator_does_not_automatically_win(self):
        campaign = PromotionCampaignProfile(
            "Indie Game", genres=("indie",), preferred_streamer_tiers=("emerging",),
            promotion_objective="awareness",
        )
        streamers = [
            StreamerProfile(
                "huge", {"indie"}, "en", "large", 100_000,
                category_history=("indie",), median_viewers=100_000, peak_viewers=200_000,
                primary_category_share=0.9, viewer_volatility=0.1, observation_count=20,
            ),
            StreamerProfile(
                "reachable", {"indie"}, "en", "emerging", 2_000,
                category_history=("indie",), median_viewers=1_800, peak_viewers=4_000,
                primary_category_share=0.8, viewer_volatility=0.1, observation_count=20,
            ),
        ]

        results = rank_streamers(campaign, streamers)

        self.assertEqual(results[0].streamer_id, "reachable")

    def test_language_mismatch_is_not_a_successful_match(self):
        campaign = PromotionCampaignProfile("Game", target_languages=("en", "es"))
        match = StreamerProfile(
            "en", {"game"}, "en", "mid-size", 2_000,
            median_viewers=1_800, peak_viewers=4_000, observation_count=8,
        )
        mismatch = StreamerProfile(
            "fr", {"game"}, "fr", "mid-size", 2_000,
            median_viewers=1_800, peak_viewers=4_000, observation_count=8,
        )
        missing = StreamerProfile(
            "missing", {"game"}, "", "mid-size", 2_000,
            median_viewers=1_800, peak_viewers=4_000, observation_count=8,
        )

        results = rank_streamers(campaign, [match, mismatch, missing])
        by_id = {item.streamer_id: item for item in results}

        self.assertEqual(by_id["fr"].components.language_fit, 0.0)
        self.assertLess(by_id["fr"].components.language_fit, by_id["en"].components.language_fit)
        self.assertLess(by_id["fr"].score, by_id["en"].score)
        self.assertTrue(any("language" in caution.lower() for caution in by_id["fr"].cautions))
        self.assertTrue(any("missing" in caution.lower() for caution in by_id["missing"].cautions))

    def test_preferred_tier_changes_audience_suitability(self):
        campaign = PromotionCampaignProfile("Game", preferred_streamer_tiers=("emerging",))
        streamers = [
            StreamerProfile("emerging", {"game"}, "en", "emerging", 2_000, median_viewers=1_800, observation_count=8),
            StreamerProfile("large", {"game"}, "en", "large", 50_000, median_viewers=50_000, observation_count=8),
        ]

        results = rank_streamers(campaign, streamers)
        by_id = {item.streamer_id: item for item in results}

        self.assertGreater(
            by_id["emerging"].components.audience_suitability,
            by_id["large"].components.audience_suitability,
        )

    def test_missing_growth_is_unavailable_and_reduces_confidence(self):
        campaign = PromotionCampaignProfile("Game")
        streamer = StreamerProfile(
            "no-growth", {"game"}, "en", "emerging", 2_000,
            median_viewers=1_800, peak_viewers=4_000, observation_count=8,
        )

        result = rank_streamers(campaign, [streamer])[0]

        self.assertEqual(result.components.momentum, 0.0)
        self.assertIn("momentum", result.unavailable_components)
        self.assertTrue(any("momentum" in caution.lower() for caution in result.cautions))
        self.assertLess(result.confidence_score, 0.8)

    def test_limited_observations_reduce_confidence_and_add_caution(self):
        campaign = PromotionCampaignProfile("Game")
        complete = StreamerProfile(
            "complete", {"game"}, "en", "emerging", 2_000,
            median_viewers=1_800, peak_viewers=4_000, observation_count=10,
            source_mode="Live",
        )
        streamer = StreamerProfile(
            "limited", {"game"}, "en", "emerging", 2_000,
            median_viewers=1_800, peak_viewers=4_000, observation_count=1,
            source_mode="Demo", partial_coverage=True,
        )

        by_id = {item.streamer_id: item for item in rank_streamers(campaign, [complete, streamer])}
        result = by_id["limited"]

        self.assertLess(result.confidence_score, by_id["complete"].confidence_score)
        self.assertLess(result.confidence_score, 0.5)
        self.assertTrue(any("observation" in caution.lower() for caution in result.cautions))
        self.assertTrue(any("partial" in caution.lower() for caution in result.cautions))

    def test_confidence_is_separate_from_fit_score_and_output_is_complete(self):
        campaign = PromotionCampaignProfile(
            "Game", genres=("action",), target_languages=("en",),
            preferred_streamer_tiers=("emerging",), promotion_objective="launch promotion",
        )
        streamer = StreamerProfile(
            "creator", {"action"}, "en", "emerging", 2_000,
            name="Creator Name", category_history=("Game",), median_viewers=1_800,
            peak_viewers=4_000, primary_category="Game", primary_category_share=0.7,
            viewer_volatility=0.2, observation_count=10, seven_day_growth=0.2,
            source_mode="Live", profile_image_url="https://example.test/profile.png",
            twitch_channel_url="https://twitch.tv/creator", observed_at="2026-08-01T00:00:00Z",
        )

        result = rank_streamers(campaign, [streamer])[0]

        self.assertNotEqual(result.score, round(result.confidence_score * 100, 1))
        self.assertEqual(result.average_viewers, 2_000)
        self.assertEqual(result.median_viewers, 1_800)
        self.assertEqual(result.peak_viewers, 4_000)
        self.assertEqual(result.primary_category, "Game")
        self.assertEqual(result.primary_category_share, 0.7)
        self.assertEqual(result.language, "en")
        self.assertEqual(result.channel_tier, "emerging")
        self.assertEqual(result.seven_day_growth, 0.2)
        self.assertEqual(result.profile_image_url, "https://example.test/profile.png")
        self.assertEqual(result.twitch_channel_url, "https://twitch.tv/creator")
        self.assertEqual(result.source_mode, "Live")
        self.assertEqual(result.observed_at, "2026-08-01T00:00:00Z")
        self.assertTrue(any("not a sales" in caution.lower() for caution in result.cautions))

    def test_sorting_uses_score_confidence_name_then_id(self):
        campaign = PromotionCampaignProfile("Game")
        streamers = [
            StreamerProfile("b", {"game"}, "en", "emerging", 2_000, name="Same", median_viewers=1_800, observation_count=10, source_mode="Live"),
            StreamerProfile("a", {"game"}, "en", "emerging", 2_000, name="Same", median_viewers=1_800, observation_count=10, source_mode="Live"),
            StreamerProfile("c", {"game"}, "en", "emerging", 2_000, name="Alpha", median_viewers=1_800, observation_count=10, source_mode="Live"),
        ]

        results = rank_streamers(campaign, streamers)

        self.assertEqual([item.streamer_id for item in results], ["c", "a", "b"])

    def test_fit_scores_are_bounded_from_zero_to_one_hundred(self):
        campaign = PromotionCampaignProfile("Game")
        streamers = [
            StreamerProfile("empty", set(), "", "emerging", 0),
            StreamerProfile("active", {"game"}, "en", "mid-size", 100_000, median_viewers=100_000, observation_count=20),
        ]

        results = rank_streamers(campaign, streamers)

        for result in results:
            self.assertGreaterEqual(result.score, 0)
            self.assertLessEqual(result.score, 100)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from gamepulse.streamer_fit import PromotionCampaignProfile, StreamerProfile, rank_streamers
from gamepulse.ui.developer import filter_creator_fits_by_tier
from gamepulse.ui.developer_components import render_creator_comparison, render_creator_fit_card


class _FakeStreamlit:
    def __init__(self):
        self.markdowns = []
        self.infos = []

    def markdown(self, value, unsafe_allow_html=False):
        self.markdowns.append(value)

    def info(self, value):
        self.infos.append(value)


def _fit_fixture(streamer_id, tier):
    return SimpleNamespace(streamer_id=streamer_id, channel_tier=tier)


class DeveloperValidationTests(unittest.TestCase):
    def test_creator_tier_filter_accepts_normalized_selected_tier(self):
        fits = [
            _fit_fixture("emerging-creator", "emerging"),
            _fit_fixture("mid-size-creator", "mid-size"),
            _fit_fixture("large-creator", "large"),
        ]

        filtered = filter_creator_fits_by_tier(fits, ["MID SIZE"])

        self.assertEqual([fit.streamer_id for fit in filtered], ["mid-size-creator"])

    def test_public_fit_output_separates_direct_history_from_similar_audience_overlap(self):
        campaign = PromotionCampaignProfile("Target Game", similar_games=("Similar Game",))
        fits = rank_streamers(
            campaign,
            [
                StreamerProfile(
                    "direct", {"variety"}, "en", "mid-size", 3_000,
                    name="Direct Creator", category_history=("Target Game",),
                    median_viewers=2_500, peak_viewers=6_000, observation_count=8,
                ),
                StreamerProfile(
                    "similar", {"variety"}, "en", "mid-size", 3_000,
                    name="Similar Creator", category_history=("Similar Game",),
                    similar_game_history=("Similar Game",), median_viewers=2_500,
                    peak_viewers=6_000, observation_count=8,
                ),
            ],
        )
        by_id = {fit.streamer_id: fit for fit in fits}

        self.assertEqual(by_id["direct"].direct_game_matches, ("Target Game",))
        self.assertEqual(by_id["direct"].similar_game_matches, ())
        self.assertEqual(by_id["similar"].direct_game_matches, ())
        self.assertEqual(by_id["similar"].similar_game_matches, ("Similar Game",))

        direct_st = _FakeStreamlit()
        similar_st = _FakeStreamlit()
        render_creator_fit_card(direct_st, by_id["direct"])
        render_creator_fit_card(similar_st, by_id["similar"])

        direct_markup = direct_st.markdowns[-1]
        similar_markup = similar_st.markdowns[-1]
        self.assertIn("Direct selected-game history", direct_markup)
        self.assertIn("Target Game", direct_markup)
        self.assertNotIn("Similar-game audience overlap", direct_markup)
        self.assertIn("Similar-game audience overlap", similar_markup)
        self.assertIn("Similar Game", similar_markup)
        self.assertNotIn("Direct selected-game history", similar_markup)

    def test_missing_observation_data_reduces_public_confidence(self):
        campaign = PromotionCampaignProfile("Target Game")
        common = dict(
            categories={"Target Game"}, language="en", tier="mid-size", average_viewers=3_000,
            median_viewers=2_500, peak_viewers=6_000, primary_category="Target Game",
            primary_category_share=0.8, viewer_volatility=0.2, source_mode="Live",
            observed_at="2026-08-01T00:00:00Z",
        )
        complete = StreamerProfile("complete", observation_count=10, **common)
        incomplete = StreamerProfile("incomplete", observation_count=1, **common)

        by_id = {
            fit.streamer_id: fit
            for fit in rank_streamers(
                campaign,
                [complete, incomplete],
                now=datetime(2026, 8, 2, tzinfo=timezone.utc),
            )
        }

        self.assertLess(by_id["incomplete"].confidence_score, by_id["complete"].confidence_score)
        self.assertTrue(any("limited observations" in item.casefold() for item in by_id["incomplete"].cautions))

    def test_empty_filtered_recommendations_show_public_comparison_state(self):
        filtered = filter_creator_fits_by_tier([_fit_fixture("emerging-creator", "emerging")], ["large"])
        st = _FakeStreamlit()

        render_creator_comparison(st, filtered)

        self.assertEqual(st.infos, ["Select two or three recommended streamers to compare them."])

    def test_developer_mode_explains_empty_recommendation_filters(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()
        app.radio[0].set_value("Developer").run()

        tiers = next(item for item in app.multiselect if item.label == "Preferred streamer tiers")
        tiers.set_value(["large"]).run()

        self.assertFalse(app.exception)
        self.assertIn("No streamers match the selected campaign filters.", [item.value for item in app.info])

    def test_developer_mode_exposes_six_separate_campaign_summary_fields(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()
        app.radio[0].set_value("Developer").run()

        self.assertFalse(app.exception)
        markdown = "\n".join(item.value for item in app.markdown)
        for label in (
            "Selected game",
            "Promotion objective",
            "Target language",
            "Preferred creator tier",
            "Similar-game option",
            "Budget positioning",
        ):
            self.assertIn(label, markdown)


if __name__ == "__main__":
    unittest.main()

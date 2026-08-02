import unittest
from types import SimpleNamespace

from gamepulse.market_analysis import DeveloperOpportunity, DeveloperOpportunityComponents
from gamepulse.ui.developer_components import (
    creator_fits_csv,
    render_comparable_card,
    render_creator_comparison,
    render_creator_fit_card,
    render_developer_hero,
    render_opportunity_summary,
    render_signal_card,
)


class FakeStreamlit:
    def __init__(self):
        self.markdowns = []
        self.captions = []
        self.infos = []

    def markdown(self, value, unsafe_allow_html=False):
        self.markdowns.append((value, unsafe_allow_html))

    def caption(self, value):
        self.captions.append(value)

    def info(self, value):
        self.infos.append(value)


class DeveloperComponentTests(unittest.TestCase):
    def test_hero_has_accessible_artwork_fallback_and_developer_label(self):
        st = FakeStreamlit()
        game = SimpleNamespace(
            name="Demo Game",
            header_image_url=None,
            release_date="2025-01-01",
            price_usd=19.99,
            review_score=0.91,
            genres=("Action",),
            tags=("Co-op",),
        )

        render_developer_hero(st, game)

        markup = st.markdowns[0][0]
        self.assertIn("Developer intelligence", markup)
        self.assertIn("Artwork unavailable", markup)
        self.assertIn('aria-labelledby="gp-developer-selected-game"', markup)

    def test_opportunity_summary_exposes_score_components_and_disclaimer(self):
        st = FakeStreamlit()
        opportunity = DeveloperOpportunity(
            score=72,
            score_band="Promising signal",
            components=DeveloperOpportunityComponents(0.8, 0.9, 0.5, 0.6, 0.4),
            reasons=("Public audience signal is visible.", "Creator coverage is available."),
            disclaimer="This is not verified sales.",
        )

        render_opportunity_summary(st, opportunity)

        markup = "\n".join(item[0] for item in st.markdowns)
        self.assertIn("Opportunity score", markup)
        self.assertIn("72/100", markup)
        self.assertIn("Audience", markup)
        self.assertIn("Public audience signal", markup)
        self.assertIn("not verified sales", markup)
        self.assertNotRegex(markup, r'\n\s{4,}<div class="gp-developer-component">')

    def test_signal_and_evidence_cards_keep_labels_visible(self):
        st = FakeStreamlit()
        render_signal_card(st, "Peak CCU", "12,345", "Observed concurrent players")
        render_comparable_card(st, {"name": "Peer Game", "price_usd": 9.99, "review_score": 0.88, "overlap": 3})
        render_creator_fit_card(st, SimpleNamespace(streamer_id="CreatorOne", score=61.0, score_band="Promising fit", reasons=("tag overlap",)))

        markup = "\n".join(item[0] for item in st.markdowns)
        self.assertIn("12,345", markup)
        self.assertIn("Peer Game", markup)
        self.assertIn("CreatorOne", markup)
        self.assertIn("tag overlap", markup)

    def test_creator_fit_card_formats_public_fit_evidence_and_cautions(self):
        st = FakeStreamlit()
        fit = SimpleNamespace(
            streamer_id="creator-1",
            streamer_name="Creator <One>",
            score=78.5,
            score_band="Strong fit",
            confidence_score=0.62,
            confidence_band="Moderate confidence",
            average_viewers=2000,
            median_viewers=1800,
            peak_viewers=6500,
            primary_category="Example Game",
            primary_category_share=0.75,
            language="en",
            channel_tier="emerging",
            seven_day_growth=0.12,
            reasons=("historical category match",),
            cautions=("limited observations",),
            components=SimpleNamespace(values={"category_history_fit": 0.9, "similar_game_fit": 0.6}),
            source_mode="Demo",
            observed_at="2026-08-01T00:00:00Z",
            twitch_channel_url="https://twitch.tv/creator-one",
            profile_image_url=None,
        )

        render_creator_fit_card(st, fit)

        markup = st.markdowns[-1][0]
        self.assertIn("Promotion Fit Score", markup)
        self.assertIn("78.5/100", markup)
        self.assertIn("Creator &lt;One&gt;", markup)
        self.assertIn("Moderate confidence", markup)
        self.assertIn("limited observations", markup)
        self.assertIn("Demo", markup)
        self.assertIn("Category history fit", markup)

    def test_creator_fit_card_labels_provenance_and_data_limitations(self):
        st = FakeStreamlit()
        fit = SimpleNamespace(
            streamer_id="creator-1",
            streamer_name="Creator One",
            score=61.0,
            score_band="Promising fit",
            confidence_score=0.38,
            confidence_band="Low confidence",
            data_source="Historical",
            observed_at="2025-01-01T00:00:00Z",
            data_limitations=("Historical observations may not reflect current creator activity.",),
            reasons=("historical category match",),
            cautions=(),
            components=SimpleNamespace(values={}),
        )

        render_creator_fit_card(st, fit)

        markup = st.markdowns[-1][0]
        self.assertIn("Data source: Historical", markup)
        self.assertIn("Observation date: 2025-01-01T00:00:00Z", markup)
        self.assertIn("Confidence level: 38%", markup)
        self.assertIn("Data limitations:", markup)
        self.assertIn("Historical observations may not reflect current creator activity.", markup)

    def test_creator_fit_card_explains_selection_and_required_limitations(self):
        st = FakeStreamlit()
        fit = SimpleNamespace(
            streamer_id="creator-1",
            streamer_name="Creator One",
            score=61.0,
            score_band="Promising fit",
            confidence_score=0.38,
            confidence_band="Low confidence",
            average_viewers=2000,
            median_viewers=1800,
            peak_viewers=6500,
            primary_category="Example Game",
            primary_category_share=0.75,
            channel_tier="emerging",
            reasons=("matches Example Game category",),
            cautions=("Limited observations reduce confidence in the fit.",),
            unavailable_components=("similar_game_fit",),
            partial_coverage=True,
            components=SimpleNamespace(values={
                "category_history_fit": 0.8,
                "similar_game_fit": 0.0,
                "audience_suitability": 0.9,
            }),
        )

        render_creator_fit_card(st, fit)

        markup = st.markdowns[-1][0]
        self.assertIn("Recommended because:", markup)
        self.assertIn("Game/category similarity:", markup)
        self.assertIn("Audience suitability:", markup)
        self.assertIn("Available viewer evidence:", markup)
        self.assertIn("Limitations:", markup)
        self.assertIn("Missing history:", markup)
        self.assertIn("Partial data:", markup)
        self.assertIn("Low confidence:", markup)
        self.assertIn("Median viewers: 1,800", markup)
        self.assertIn("Partial coverage", markup)

    def test_creator_fit_card_explains_similar_game_match_and_audience_overlap(self):
        st = FakeStreamlit()
        fit = SimpleNamespace(
            streamer_id="creator-1",
            streamer_name="Creator One",
            score=61.0,
            score_band="Promising fit",
            confidence_score=0.62,
            confidence_band="Moderate confidence",
            average_viewers=2000,
            median_viewers=1800,
            channel_tier="mid-size",
            similar_game_matches=("Stardew Valley",),
            components=SimpleNamespace(values={
                "category_history_fit": 0.0,
                "similar_game_fit": 1.0,
                "audience_suitability": 0.9,
            }),
        )

        render_creator_fit_card(st, fit)

        markup = st.markdowns[-1][0]
        self.assertIn("Match basis:", markup)
        self.assertIn("Similar-game history", markup)
        self.assertIn("Similar-game match:", markup)
        self.assertIn("Stardew Valley", markup)
        self.assertIn("Why it matters:", markup)
        self.assertIn("audience overlap", markup)
        self.assertIn("related audience", markup)
        self.assertIn("Audience suitability: 90%", markup)

    def test_creator_fit_card_uses_plain_language_match_labels_and_top_reasons(self):
        st = FakeStreamlit()
        fit = SimpleNamespace(
            streamer_id="creator-1",
            streamer_name="Creator One",
            score=61.0,
            score_band="Promising fit",
            confidence_score=0.62,
            confidence_band="Moderate confidence",
            direct_game_matches=("Target Game",),
            similar_game_matches=("Similar Game",),
            reasons=("matches Target Game category", "audience size fits the campaign's preferred streamer range"),
            cautions=("This is directional public-signal fit, not a sales or conversion prediction.",),
            components=SimpleNamespace(values={"audience_suitability": 0.9}),
            source_mode="Demo",
            source_name="Demo fixture",
            observed_at="2026-08-01T00:00:00Z",
        )

        render_creator_fit_card(st, fit)

        markup = st.markdowns[-1][0]
        self.assertIn("Direct selected-game history", markup)
        self.assertIn("Similar-game audience overlap", markup)
        self.assertIn("General audience suitability", markup)
        self.assertIn("Top reasons", markup)
        self.assertIn("Limitations", markup)
        self.assertIn("Data source", markup)
        self.assertIn("not a sales or conversion prediction", markup)

    def test_creator_fit_card_exposes_exact_match_type_reasons_confidence_and_metadata(self):
        fixtures = (
            ("direct_game_matches", ("Target Game",), "Direct Game Match"),
            ("similar_game_matches", ("Similar Game",), "Similar Game Specialist"),
            ("audience_only", (), "Audience Similarity Match"),
        )

        for fixture_name, matches, expected_match_type in fixtures:
            with self.subTest(fixture_name=fixture_name):
                st = FakeStreamlit()
                fit_values = dict(
                    streamer_id="creator-1",
                    streamer_name="Creator One",
                    score=61.0,
                    score_band="Promising fit",
                    confidence_score=0.62,
                    confidence_band="Moderate confidence",
                    reasons=("matches the campaign audience",),
                    cautions=("Directional public-signal evidence only.",),
                    source_mode="Demo",
                    source_name="Demo fixture",
                    observed_at="2026-08-01T00:00:00Z",
                    components=SimpleNamespace(values={"audience_suitability": 0.9}),
                )
                if fixture_name == "audience_only":
                    fit_values["direct_game_matches"] = ()
                    fit_values["similar_game_matches"] = ()
                else:
                    fit_values[fixture_name] = matches

                render_creator_fit_card(st, SimpleNamespace(**fit_values))

                markup = st.markdowns[-1][0]
                self.assertIn(f"<strong>{expected_match_type}</strong>", markup)
                self.assertIn("Recommended because:", markup)
                self.assertIn("matches the campaign audience", markup)
                self.assertIn("Confidence level: 62%", markup)
                self.assertIn("Data limitations:", markup)
                self.assertIn("Directional public-signal evidence only.", markup)
                self.assertIn("Data source: Demo - Demo fixture", markup)
                self.assertIn("Observation date: 2026-08-01T00:00:00Z", markup)

    def test_creator_comparison_shows_two_or_three_fit_rows(self):
        st = FakeStreamlit()
        fits = [
            SimpleNamespace(
                streamer_id=identifier,
                streamer_name=name,
                score=score,
                confidence_score=confidence,
                components=SimpleNamespace(values={"category_history_fit": 0.8, "similar_game_fit": 0.4}),
                average_viewers=1000,
                language="en",
            )
            for identifier, name, score, confidence in (("a", "Alpha", 70, 0.8), ("b", "Beta", 65, 0.7))
        ]

        render_creator_comparison(st, fits)

        markup = st.markdowns[-1][0]
        self.assertIn("Streamer comparison", markup)
        self.assertIn("Category-history fit", markup)
        self.assertIn("Alpha", markup)
        self.assertIn("Beta", markup)

    def test_creator_csv_contains_derived_fields_only(self):
        fit = SimpleNamespace(
            streamer_id="creator-1",
            streamer_name="Creator One",
            score=78.5,
            score_band="Strong fit",
            confidence_score=0.62,
            confidence_band="Moderate confidence",
            average_viewers=2000,
            median_viewers=1800,
            peak_viewers=6500,
            primary_category="Example Game",
            primary_category_share=0.75,
            language="en",
            channel_tier="emerging",
            seven_day_growth=0.12,
            reasons=("historical category match",),
            cautions=("limited observations",),
            components=SimpleNamespace(values={"category_history_fit": 0.9}),
            source_mode="Demo",
            observed_at="2026-08-01T00:00:00Z",
            twitch_channel_url="https://twitch.tv/creator-one",
        )

        csv_text = creator_fits_csv([fit])

        self.assertIn("streamer_id,streamer_name,fit_score", csv_text)
        self.assertIn("Creator One", csv_text)
        self.assertIn("Demo", csv_text)
        self.assertNotIn("token", csv_text.lower())
        self.assertNotIn("credential", csv_text.lower())

    def test_empty_creator_state_is_explicit(self):
        st = FakeStreamlit()

        render_creator_comparison(st, [])

        self.assertIn("Select two or three", st.infos[0])


if __name__ == "__main__":
    unittest.main()

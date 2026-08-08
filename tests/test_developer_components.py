import unittest
from types import SimpleNamespace

from gamepulse.market_analysis import DeveloperOpportunity, DeveloperOpportunityComponents
from gamepulse.ui.developer_components import (
    render_comparable_card,
    render_creator_fit_card,
    render_developer_hero,
    render_opportunity_summary,
    render_signal_card,
)


class FakeStreamlit:
    def __init__(self):
        self.markdowns = []
        self.captions = []

    def markdown(self, value, unsafe_allow_html=False):
        self.markdowns.append((value, unsafe_allow_html))

    def caption(self, value):
        self.captions.append(value)


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


if __name__ == "__main__":
    unittest.main()

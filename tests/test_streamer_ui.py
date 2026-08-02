import unittest
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from gamepulse.providers.twitch import Snapshot
from gamepulse.streamer_opportunity import evaluate_snapshot_freshness
from gamepulse.ui.streamer_components import (
    render_category_deep_dive,
    render_creator_landscape,
    render_opportunity_card,
    render_opportunity_empty_state,
    render_snapshot_status,
)


class _FakeStreamlit:
    def __init__(self):
        self.infos = []
        self.warnings = []
        self.successes = []
        self.captions = []
        self.markdowns = []
        self.errors = []
        self.plotly_figures = []

    def info(self, value):
        self.infos.append(value)

    def warning(self, value):
        self.warnings.append(value)

    def success(self, value):
        self.successes.append(value)

    def caption(self, value):
        self.captions.append(value)

    def markdown(self, value, **_kwargs):
        self.markdowns.append(value)

    def error(self, value):
        self.errors.append(value)

    def plotly_chart(self, figure, **_kwargs):
        self.plotly_figures.append(figure)


class StreamerModeStateTests(unittest.TestCase):
    def test_stale_snapshot_is_visible_as_directional_data(self):
        fake = _FakeStreamlit()
        snapshot = Snapshot("Demo", "2026-07-20T00:00:00Z", "fixture", [])

        render_snapshot_status(fake, snapshot, evaluate_snapshot_freshness(snapshot))

        self.assertEqual(len(fake.warnings), 1)
        self.assertIn("directional", fake.warnings[0])

    def test_live_snapshot_keeps_live_source_label_visible(self):
        fake = _FakeStreamlit()
        snapshot = Snapshot("Live", "2026-08-02T12:00:00Z", "Twitch Helix", [])

        render_snapshot_status(fake, snapshot, evaluate_snapshot_freshness(snapshot))

        self.assertEqual(len(fake.successes), 1)
        self.assertIn("Live Twitch", fake.successes[0])
        self.assertIn("Twitch Helix", fake.captions[0])

    def test_opportunity_card_explains_score_and_missing_artwork(self):
        fake = _FakeStreamlit()
        opportunity = SimpleNamespace(
            name="Example Game",
            score=72,
            score_band="Promising opportunity",
            viewer_count=10000,
            channel_count=100,
            viewer_to_channel=100.0,
            reasons=("recent growth signal is positive",),
            cautions=("No verified Steam mapping",),
            confidence_score=0.68,
            confidence_band="Medium confidence",
            trend_direction="rising",
            source_mode="Demo",
            observed_at="2026-08-01T12:00:00Z",
        )

        render_opportunity_card(fake, opportunity)

        self.assertIn("72/100", fake.markdowns[0])
        self.assertIn("Promising opportunity", fake.markdowns[0])
        self.assertIn("recent growth signal is positive", fake.markdowns[0])
        self.assertIn("Confidence", fake.markdowns[0])
        self.assertIn("No verified Steam mapping", fake.markdowns[0])

    def test_empty_opportunity_state_explains_next_action(self):
        fake = _FakeStreamlit()

        render_opportunity_empty_state(fake, "No categories match the filters.")

        self.assertEqual(fake.infos, ["No categories match the filters."])
        self.assertIn("refresh", fake.captions[0])

    def test_deep_dive_formats_observed_metrics_and_history(self):
        fake = _FakeStreamlit()
        trend = SimpleNamespace(
            name='Category <unsafe>',
            viewer_count=1200,
            channel_count=24,
            viewer_to_channel=50.0,
            rank=7,
            top_one_viewer_share=0.42,
            top_five_viewer_share=0.78,
            average_stream_age_seconds=3600,
            language_distribution={"en": 18, "de": 6},
            contributing_stream_rows=24,
            pages_collected=2,
            partial_coverage=True,
            observed_total=True,
            source_mode="Demo",
            observed_at="2026-08-01T12:00:00Z",
        )
        history = (
            {"observed_at": "2026-07-25T12:00:00Z", "viewer_count": 900, "channel_count": 20, "viewer_to_channel": 45.0},
            {"observed_at": "2026-08-01T12:00:00Z", "viewer_count": 1200, "channel_count": 24, "viewer_to_channel": 50.0},
        )

        render_category_deep_dive(fake, trend, history=history, freshness_label="Demo · observed values")

        output = "\n".join(fake.markdowns + fake.captions + fake.infos + fake.warnings)
        self.assertIn("Category &lt;unsafe&gt;", output)
        self.assertIn("Observed viewers", output)
        self.assertIn("Viewer concentration", output)
        self.assertIn("Demo", output)
        self.assertEqual(len(fake.plotly_figures), 1)

    def test_creator_landscape_is_informational_and_escapes_text(self):
        fake = _FakeStreamlit()
        snapshot = Snapshot(
            "Demo",
            "2026-08-01T12:00:00Z",
            "fixture",
            [
                SimpleNamespace(
                    name="Creator <unsafe>",
                    viewer_count=321,
                    channel_size_tier="emerging",
                    language="en",
                    tags=("speedrun",),
                    login_name="creator_one",
                    profile_image_url="https://cdn.example/image.png",
                    game_name="Example Category",
                )
            ],
        )

        render_creator_landscape(fake, snapshot)

        output = "\n".join(fake.markdowns + fake.captions + fake.infos)
        self.assertIn("informational", output)
        self.assertIn("Creator &lt;unsafe&gt;", output)
        self.assertIn("321", output)
        self.assertIn("https://www.twitch.tv/creator_one", output)


class StreamerModeUITests(unittest.TestCase):
    def test_streamer_mode_exposes_opportunity_dashboard(self):
        app = AppTest.from_file("app.py", default_timeout=15).run()
        app.radio[0].set_value("Streamer").run()

        self.assertFalse(app.exception)
        self.assertTrue(any(item.value == "Streamer Mode" for item in app.title))
        self.assertIn("Your channel size", [item.label for item in app.selectbox])
        self.assertIn("What are you optimizing for?", [item.label for item in app.selectbox])
        self.assertIn("Preferred languages", [item.label for item in app.multiselect])
        self.assertIn("Preferred Steam genres", [item.label for item in app.multiselect])
        self.assertIn("Preferred Steam tags", [item.label for item in app.multiselect])
        self.assertIn("Preferred Twitch tags", [item.label for item in app.multiselect])
        self.assertIn("Minimum observed viewers", [item.label for item in app.slider])
        self.assertIn("Maximum competition", [item.label for item in app.slider])
        self.assertIn("Include Twitch-only categories", [item.label for item in app.checkbox])
        self.assertIn("Game Opportunities", [item.value for item in app.subheader])
        self.assertIn("Category Deep Dive", [item.value for item in app.subheader])
        self.assertIn("Creator Landscape", [item.value for item in app.subheader])
        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("Opportunity", markdown)
        self.assertIn("Observed viewers", markdown)
        self.assertIn("DemoClassicFPSCreator", markdown)


if __name__ == "__main__":
    unittest.main()

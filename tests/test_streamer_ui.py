import unittest
from types import SimpleNamespace

try:
    from streamlit.testing.v1 import AppTest
except ModuleNotFoundError:  # Desktop branch intentionally has no Streamlit runtime.
    AppTest = None

from gamepulse.providers.twitch import Snapshot
from gamepulse.streamer_opportunity import evaluate_snapshot_freshness
from gamepulse.ui.streamer_components import render_opportunity_card, render_snapshot_status


class _FakeStreamlit:
    def __init__(self):
        self.infos = []
        self.warnings = []
        self.successes = []
        self.captions = []
        self.markdowns = []

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


class StreamerModeStateTests(unittest.TestCase):
    def test_stale_snapshot_is_visible_as_directional_data(self):
        fake = _FakeStreamlit()
        snapshot = Snapshot("Demo", "2026-07-20T00:00:00Z", "fixture", [])

        render_snapshot_status(fake, snapshot, evaluate_snapshot_freshness(snapshot))

        self.assertEqual(len(fake.warnings), 1)
        self.assertIn("directional", fake.warnings[0])

    def test_opportunity_card_explains_score_and_missing_artwork(self):
        fake = _FakeStreamlit()
        opportunity = SimpleNamespace(
            name="Example Game",
            score=0.72,
            score_band="Promising opportunity",
            viewer_count=10000,
            channel_count=100,
            viewer_to_channel=100.0,
            reasons=("recent growth signal is positive",),
        )

        render_opportunity_card(fake, opportunity)

        self.assertIn("72/100", fake.markdowns[0])
        self.assertIn("Promising opportunity", fake.markdowns[0])
        self.assertIn("recent growth signal is positive", fake.markdowns[0])


@unittest.skipIf(AppTest is None, "legacy Streamlit UI is not installed on the desktop branch")
class StreamerModeUITests(unittest.TestCase):
    def test_streamer_mode_exposes_opportunity_dashboard(self):
        app = AppTest.from_file("app.py", default_timeout=15).run()
        app.radio[0].set_value("Streamer").run()

        self.assertFalse(app.exception)
        self.assertTrue(any(item.value == "Streamer Mode" for item in app.title))
        self.assertIn("Your channel size", [item.label for item in app.selectbox])
        self.assertIn("Preferred category tags", [item.label for item in app.multiselect])
        self.assertIn("Top opportunities", [item.value for item in app.subheader])
        self.assertIn("Trending creators", [item.value for item in app.subheader])
        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("Opportunity", markdown)
        self.assertIn("Observed viewers", markdown)
        self.assertIn("DemoClassicFPSCreator", markdown)


if __name__ == "__main__":
    unittest.main()

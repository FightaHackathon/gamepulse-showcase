import unittest

try:
    from streamlit.testing.v1 import AppTest
except ModuleNotFoundError:  # Desktop branch intentionally has no Streamlit runtime.
    AppTest = None


@unittest.skipIf(AppTest is None, "legacy Streamlit UI is not installed on the desktop branch")
class PlayerModeUITests(unittest.TestCase):
    def _player(self):
        app = AppTest.from_file("app.py", default_timeout=15).run()
        app.radio[0].set_value("Player").run()
        return app

    def test_player_mode_exposes_guided_personalization_and_match_language(self):
        app = self._player()

        self.assertFalse(app.exception)
        self.assertTrue(any(item.value == "Player Mode" for item in app.title))
        self.assertIn("Analyze public profile", [item.label for item in app.button])
        self.assertIn("Preferred tags", [item.label for item in app.multiselect])
        self.assertIn("Preferred genres", [item.label for item in app.multiselect])
        self.assertIn("Discovery", [item.label for item in app.radio])
        self.assertIn("Operating system", [item.label for item in app.selectbox])

        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("Match", markdown)
        self.assertIn("View on Steam", markdown)

    def test_player_mode_can_apply_linux_filter_without_crashing(self):
        app = self._player()
        operating_system = next(item for item in app.selectbox if item.label == "Operating system")

        operating_system.set_value("Linux").run()

        self.assertFalse(app.exception)
        self.assertIn("Recommended games", [item.value for item in app.subheader])

    def test_player_mode_shows_a_broader_recommendation_window(self):
        app = self._player()

        card_count = sum('<article class="gp-player-card' in item.value for item in app.markdown)

        self.assertGreaterEqual(card_count, 24)
        ranked_caption = next(item.value for item in app.caption if "games ranked" in item.value)
        self.assertGreaterEqual(int(ranked_caption.split()[0]), 300)

    def test_player_mode_can_open_game_details_and_review_catalogue(self):
        app = self._player()

        view_details = [item for item in app.button if item.label == "View details"]
        self.assertTrue(view_details)
        view_details[0].click().run()

        self.assertFalse(app.exception)
        self.assertIn("Review catalogue", [item.value for item in app.subheader])
        self.assertTrue(any("newest public reviews" in item.value for item in app.caption))


if __name__ == "__main__":
    unittest.main()

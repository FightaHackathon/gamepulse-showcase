import unittest

from streamlit.testing.v1 import AppTest


class DeveloperModeUITests(unittest.TestCase):
    def test_developer_mode_exposes_comparables_and_bounded_fit_scores(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()
        app.radio[0].set_value("Developer").run()

        self.assertFalse(app.exception)
        self.assertTrue(any(item.value == "Developer Mode" for item in app.title))
        self.assertIn("Opportunity score", [item.value for item in app.subheader])
        self.assertIn("Public market signals", [item.value for item in app.subheader])
        self.assertIn("Comparable games", [item.value for item in app.subheader])
        self.assertIn("Review themes", [item.value for item in app.subheader])
        self.assertIn("30-day interest forecast", [item.value for item in app.subheader])
        self.assertIn("Streamer fit shortlist", [item.value for item in app.subheader])
        selectbox_labels = [item.label for item in app.selectbox]
        multiselect_labels = [item.label for item in app.multiselect]
        slider_labels = [item.label for item in app.slider]
        checkbox_labels = [item.label for item in app.checkbox]
        self.assertIn("Promotion objective", selectbox_labels)
        self.assertIn("Budget positioning", selectbox_labels)
        self.assertIn("Target languages", multiselect_labels)
        self.assertIn("Preferred streamer tiers", multiselect_labels)
        self.assertIn("Recommendation count", slider_labels)
        self.assertIn("Require selected-game history", checkbox_labels)
        self.assertIn("Include similar-game specialists", checkbox_labels)
        self.assertEqual(len(app.get("download_button")), 1)
        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("/100", markdown)
        self.assertIn("Developer intelligence · Local prepared data", markdown)
        self.assertNotIn("Developer intelligence · Live", markdown)
        self.assertIn("not verified", markdown.lower())
        self.assertNotIn("0 shared signals", markdown)
        self.assertIn("overlap score", markdown)
        self.assertTrue("Current players" in markdown or "Peak CCU" in markdown)

    def test_campaign_objective_and_filters_change_visible_recommendations(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()
        app.radio[0].set_value("Developer").run()

        objective = next(item for item in app.selectbox if item.label == "Promotion objective")
        objective.set_value("Launch promotion").run()
        self.assertIn("Launch promotion", "\n".join(item.value for item in app.caption))

        tiers = next(item for item in app.multiselect if item.label == "Preferred streamer tiers")
        tiers.set_value(["emerging"]).run()
        require_history = next(item for item in app.checkbox if item.label == "Require selected-game history")
        require_history.set_value(True).run()
        require_history = next(item for item in app.checkbox if item.label == "Require selected-game history")
        self.assertTrue(require_history.value)
        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("DemoClassicFPSCreator", markdown)
        self.assertNotIn("DemoFPSCreator", markdown)

        languages = next(item for item in app.multiselect if item.label == "Target languages")
        languages.set_value(["en"]).run()
        self.assertEqual(languages.value, ["en"])


if __name__ == "__main__":
    unittest.main()

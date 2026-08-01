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
        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("/100", markdown)
        self.assertIn("not verified", markdown.lower())
        self.assertNotIn("0 shared signals", markdown)
        self.assertIn("overlap score", markdown)
        self.assertTrue("Current players" in markdown or "Peak CCU" in markdown)


if __name__ == "__main__":
    unittest.main()

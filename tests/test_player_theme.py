import unittest

from gamepulse.ui.player_theme import PLAYER_COLORS, player_css


class PlayerThemeTests(unittest.TestCase):
    def test_approved_color_tokens_are_present(self):
        self.assertEqual(PLAYER_COLORS["canvas"], "#080D18")
        self.assertEqual(PLAYER_COLORS["surface"], "#111A2B")
        self.assertEqual(PLAYER_COLORS["primary"], "#4C8DFF")
        self.assertEqual(PLAYER_COLORS["personalization"], "#8B7CFF")
        self.assertEqual(PLAYER_COLORS["primary_text"], "#F4F7FC")

    def test_css_contains_mobile_and_reduced_motion_rules(self):
        css = player_css()
        self.assertIn("@media (max-width: 640px)", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("min-height: 44px", css)
        self.assertIn(":focus-visible", css)


if __name__ == "__main__":
    unittest.main()

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gamepulse.desktop_models import compact_number, money, percent


class DesktopFormattingTests(unittest.TestCase):
    def test_compact_number_formats_large_values(self):
        self.assertEqual(compact_number(1_250), "1.2K")
        self.assertEqual(compact_number(2_500_000), "2.5M")
        self.assertEqual(compact_number(None), "—")

    def test_money_formats_optional_values(self):
        self.assertEqual(money(19.99), "$19.99")
        self.assertEqual(money(0), "Free")
        self.assertEqual(money(None), "—")

    def test_percent_accepts_normalized_scores(self):
        self.assertEqual(percent(0.91), "91%")
        self.assertEqual(percent(None), "—")


if __name__ == "__main__":
    unittest.main()

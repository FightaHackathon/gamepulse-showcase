import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gamepulse.catalog import Catalog
from gamepulse.config import Settings
from gamepulse.desktop_app import GamePulseWindow
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


class NativeDesktopSignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.qt_app = QApplication.instance() or QApplication([])

    def _window(self) -> GamePulseWindow:
        env = {
            "TWITCH_CLIENT_ID": "",
            "TWITCH_CLIENT_SECRET": "",
            "GAME_SIGNAL_PROVIDER": "auto",
            "CREATOR_PROVIDER": "auto",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = Settings.from_env(self.root)
        return GamePulseWindow(settings, Catalog(settings.database_path))

    def test_streamer_mode_runs_without_twitch_and_uses_metric_aware_columns(self):
        window = self._window()
        try:
            window.refresh_streamer()
            headers = [
                window.streamer_table.horizontalHeaderItem(index).text()
                for index in range(window.streamer_table.columnCount())
            ]

            self.assertGreater(window.streamer_table.rowCount(), 0)
            self.assertIn("Activity", headers)
            self.assertIn("Metric", headers)
            self.assertIn("Competition", headers)
            self.assertNotIn("Viewers", headers)
            self.assertNotIn("Channels", headers)
            self.assertNotIn("Could not load Twitch", window.streamer_source.text())
            self.assertIn("Source", window.streamer_source.text())
            self.assertIn("Freshness", window.streamer_source.text())
            self.assertIn("Confidence", window.streamer_source.text())

            metric_column = headers.index("Metric")
            metric_values = {
                window.streamer_table.item(row, metric_column).text()
                for row in range(window.streamer_table.rowCount())
                if window.streamer_table.item(row, metric_column) is not None
            }
            self.assertTrue(any("Steam" in value for value in metric_values))
            self.assertFalse(any("Twitch viewers" in value for value in metric_values if "Steam" in value))
        finally:
            window.close()

    def test_developer_mode_recommends_directory_creators_without_twitch(self):
        window = self._window()
        try:
            matches = [game for game in window.catalog.search_games("Terraria", limit=25) if game.name.casefold() == "terraria"]
            self.assertTrue(matches, "Prepared catalog should contain Terraria for the desktop demo path")
            window._set_selected_game(matches[0].steam_app_id)
            window.refresh_developer()

            self.assertTrue(hasattr(window, "developer_creator_table"))
            self.assertGreater(window.developer_creator_table.rowCount(), 0)
            headers = [
                window.developer_creator_table.horizontalHeaderItem(index).text()
                for index in range(window.developer_creator_table.columnCount())
            ]
            self.assertEqual(headers, ["Creator", "Fit", "Platform", "Audience", "Source", "Why"])

            creators = [
                window.developer_creator_table.item(row, 0).text()
                for row in range(window.developer_creator_table.rowCount())
            ]
            sources = [
                window.developer_creator_table.item(row, 4).text()
                for row in range(window.developer_creator_table.rowCount())
            ]
            self.assertTrue(any("GamePulse Demo" in name for name in creators))
            self.assertTrue(any("Demo" in source for source in sources))
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

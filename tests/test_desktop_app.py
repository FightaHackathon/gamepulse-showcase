import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gamepulse.catalog import Catalog
from gamepulse.config import Settings
from gamepulse.database import connect_read_only
from gamepulse.desktop_models import compact_number, money, percent
from gamepulse.providers.steam import PlayerLibrary, SteamProviderError
from gamepulse.providers.steamspy import SteamSpyEstimate
from gamepulse.providers.twitchtracker import TwitchTrackerSummary

try:
    from PySide6.QtWidgets import QApplication
    from gamepulse.desktop_app import GamePulseWindow
    QT_IMPORT_ERROR = None
except ModuleNotFoundError as exc:
    QApplication = None
    GamePulseWindow = None
    QT_IMPORT_ERROR = str(exc)


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


@unittest.skipIf(QApplication is None, f"PySide6 unavailable: {QT_IMPORT_ERROR}")
class NativeDesktopSignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        try:
            connection = connect_read_only(
                Settings.from_env(cls.root).database_path
            )
        except Exception as exc:
            raise unittest.SkipTest(f"Prepared database unavailable: {exc}")
        else:
            connection.close()
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
            self.assertTrue(metric_values)
            self.assertTrue(
                "Prepared" in window.streamer_source.text()
                or "Steam" in window.streamer_source.text()
            )
            self.assertFalse(any("Twitch viewers" in value for value in metric_values))
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

    def test_streamer_profile_analysis_is_keyless_and_private_profiles_fall_back(self):
        window = self._window()
        try:
            class PublicSteam:
                def resolve_profile(self, _profile):
                    return "76561198000000000"

                def get_library(self, _steam_id):
                    return PlayerLibrary(
                        "76561198000000000",
                        ({"appid": window.selected_game.steam_app_id, "playtime_forever": 120},),
                        "Public Steam games page",
                        True,
                    )

            window.steam = PublicSteam()
            window.streamer_profile_url.setText("https://steamcommunity.com/id/example/")
            window.analyze_streamer_profile()
            self.assertIn("profile analyzed", window.streamer_profile_status.text())
            self.assertNotIn("Twitch", window.streamer_profile_status.text())

            class PrivateSteam:
                def resolve_profile(self, _profile):
                    raise SteamProviderError("Steam Game Details are private")

            window.steam = PrivateSteam()
            window.analyze_streamer_profile()
            self.assertIn("not publicly available", window.streamer_profile_status.text())
            self.assertIn("manual", window.streamer_interests.text().casefold())
        finally:
            window.close()

    def test_public_estimate_results_render_with_explicit_scenario_labels(self):
        window = self._window()
        try:
            window.external_estimate_app_id = window.selected_game.steam_app_id
            window._apply_external_estimates(
                TwitchTrackerSummary(
                    requested_game=window.selected_game.name,
                    game_id=None,
                    game_name=window.selected_game.name,
                    viewer_count=None,
                    channel_count=None,
                    average_viewers=1_000,
                    peak_viewers=1_500,
                    hours_watched=None,
                    source_name="TwitchTracker API",
                    observed_at="2026-08-08T00:00:00Z",
                    confidence="live",
                    caveat="TwitchTracker public summary metrics are observed category estimates.",
                ),
                SteamSpyEstimate(
                    steam_app_id=window.selected_game.steam_app_id,
                    owners_low=10_000,
                    owners_high=20_000,
                    source_name="SteamSpy appdetails API",
                    observed_at="2026-08-08T00:00:00Z",
                    confidence="estimate",
                    caveat="SteamSpy owners are non-authoritative estimates, not verified sales.",
                ),
            )

            self.assertIn("TwitchTracker", window.streamer_external_source.text())
            self.assertIn("Average audience", window.streamer_external_source.text())
            detail = window.developer_estimate_source.text().casefold()
            self.assertIn("steamspy", detail)
            self.assertIn("scenario gross", detail)
            self.assertIn("not verified units sold", detail)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

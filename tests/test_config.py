import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gamepulse.config import Settings


class SettingsTests(unittest.TestCase):
    def test_missing_credentials_select_safe_fallback_modes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True):
                settings = Settings.from_env(Path(temp_dir))

        self.assertFalse(settings.twitch_enabled)
        self.assertFalse(settings.steam_enabled)
        self.assertFalse(settings.mistral_enabled)
        self.assertEqual(settings.database_path, Path(temp_dir) / "data" / "prototype" / "gamepulse_prototype.sqlite3")

    def test_complete_credentials_enable_each_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            values = {
                "TWITCH_CLIENT_ID": "client-id",
                "TWITCH_CLIENT_SECRET": "client-secret",
                "STEAM_WEB_API_KEY": "steam-key",
                "MISTRAL_API_KEY": "mistral-key",
            }
            with patch.dict(os.environ, values, clear=True):
                settings = Settings.from_env(Path(temp_dir))

        self.assertTrue(settings.twitch_enabled)
        self.assertTrue(settings.steam_enabled)
        self.assertTrue(settings.mistral_enabled)

    def test_streamlit_cloud_secrets_enable_steam(self):
        """Cloud deployments provide secrets through st.secrets, not os.environ."""
        import streamlit as st

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True), patch.object(
                st, "secrets", {"STEAM_WEB_API_KEY": "cloud-steam-key"}
            ):
                settings = Settings.from_env(Path(temp_dir))

        self.assertTrue(settings.steam_enabled)
        self.assertEqual(settings.steam_web_api_key, "cloud-steam-key")

    def test_dotenv_file_is_loaded_from_project_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text("TWITCH_CLIENT_ID=from-dotenv\nTWITCH_CLIENT_SECRET=secret\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                settings = Settings.from_env(root)
        self.assertEqual(settings.twitch_client_id, "from-dotenv")
        self.assertTrue(settings.twitch_enabled)

    def test_twitch_collection_settings_accept_bounded_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            values = {
                "TWITCH_MAX_STREAM_PAGES": "4",
                "TWITCH_REQUEST_TIMEOUT_SECONDS": "7.5",
            }
            with patch.dict(os.environ, values, clear=True):
                settings = Settings.from_env(Path(temp_dir))

        self.assertEqual(settings.twitch_max_stream_pages, 4)
        self.assertEqual(settings.twitch_request_timeout_seconds, 7.5)

    def test_invalid_twitch_collection_settings_use_safe_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            values = {
                "TWITCH_MAX_STREAM_PAGES": "not-a-number",
                "TWITCH_REQUEST_TIMEOUT_SECONDS": "-10",
            }
            with patch.dict(os.environ, values, clear=True):
                settings = Settings.from_env(Path(temp_dir))

        self.assertEqual(settings.twitch_max_stream_pages, 3)
        self.assertEqual(settings.twitch_request_timeout_seconds, 15.0)

    def test_demo_config_exposes_curated_game_id_and_ignores_invalid_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "data" / "prototype" / "demo_config.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text('{"selected_app_id": 10}', encoding="utf-8")
            settings = Settings.from_env(root)
            self.assertEqual(settings.demo_selected_app_id, 10)

            config_path.write_text('{"selected_app_id": "not-an-app"}', encoding="utf-8")
            self.assertIsNone(settings.demo_selected_app_id)


if __name__ == "__main__":
    unittest.main()

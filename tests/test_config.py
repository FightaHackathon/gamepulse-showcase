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
            values = dict(TWITCH_CLIENT_ID="client-id", TWITCH_CLIENT_SECRET="client-secret", STEAM_WEB_API_KEY="steam-key", MISTRAL_API_KEY="mistral-key")
            with patch.dict(os.environ, values, clear=True):
                settings = Settings.from_env(Path(temp_dir))
        self.assertTrue(settings.twitch_enabled)
        self.assertTrue(settings.steam_enabled)
        self.assertTrue(settings.mistral_enabled)

    def test_dotenv_file_is_loaded_from_project_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text("TWITCH_CLIENT_ID=from-dotenv\nTWITCH_CLIENT_SECRET=secret\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                settings = Settings.from_env(root)
        self.assertEqual(settings.twitch_client_id, "from-dotenv")
        self.assertTrue(settings.twitch_enabled)


if __name__ == "__main__":
    unittest.main()

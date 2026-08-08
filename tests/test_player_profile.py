import unittest
from types import SimpleNamespace

from gamepulse.player_profile import infer_preferences
from gamepulse.providers.steam import PlayerLibrary


class _Catalog:
    def __init__(self):
        self.games = {
            10: SimpleNamespace(tags=("FPS", "Competitive"), genres=("Action",)),
            20: SimpleNamespace(tags=("RPG", "Fantasy"), genres=("Role-Playing",)),
        }

    def get_game(self, app_id):
        if app_id not in self.games:
            raise KeyError(app_id)
        return self.games[app_id]


class PlayerProfileTests(unittest.TestCase):
    def test_preferences_use_playtime_and_recent_play_and_ignore_unknown_games(self):
        library = PlayerLibrary("76561198000000000", (
            {"appid": 10, "playtime_forever": 1000, "playtime_2weeks": 0},
            {"appid": 20, "playtime_forever": 10, "playtime_2weeks": 120},
            {"appid": 999, "playtime_forever": 9999},
        ))

        preferences = infer_preferences(library, _Catalog())

        self.assertIn("fps", preferences.preferred_tags)
        self.assertIn("rpg", preferences.preferred_tags)
        self.assertEqual(preferences.preferred_genres[0], "action")
        self.assertIsNone(preferences.operating_system)

    def test_preferences_are_deterministic_and_catalogue_aware(self):
        library = PlayerLibrary("76561198000000000", (
            {"appid": 20, "playtime_forever": 100, "playtime_2weeks": 0},
            {"appid": 10, "playtime_forever": 100, "playtime_2weeks": 0},
            {"appid": 10, "playtime_forever": "not-a-number", "playtime_2weeks": 0},
            {"appid": 999, "playtime_forever": "not-a-number", "playtime_2weeks": 0},
        ))

        first = infer_preferences(library, _Catalog())
        second = infer_preferences(library, _Catalog())

        self.assertEqual(first, second)
        self.assertEqual(first.preferred_tags, ("competitive", "fps", "fantasy", "rpg"))


if __name__ == "__main__":
    unittest.main()

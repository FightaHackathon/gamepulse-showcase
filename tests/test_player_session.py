import unittest

from gamepulse.player_session import analyze_public_profile, empty_profile_session
from gamepulse.providers.steam import PlayerLibrary, SteamProviderError


class _Game:
    tags = ("RPG",)
    genres = ("Action",)


class _Catalog:
    def get_game(self, app_id):
        if app_id == 10:
            return _Game()
        raise KeyError(app_id)


class _Provider:
    def __init__(self, library=None, error=None):
        self.library = library or PlayerLibrary("76561198000000000", ({"appid": 10, "playtime_forever": 120},))
        self.error = error
        self.resolve_calls = 0
        self.library_calls = 0

    def resolve_profile(self, profile):
        self.resolve_calls += 1
        return self.library.steam_id

    def get_library(self, steam_id):
        self.library_calls += 1
        if self.error:
            raise self.error
        return self.library


class PlayerSessionTests(unittest.TestCase):
    def test_connected_profile_is_analyzed_once_and_is_reusable(self):
        provider = _Provider()

        session = analyze_public_profile("https://steamcommunity.com/profiles/76561198000000000", provider, _Catalog())

        self.assertEqual(session.status, "connected")
        self.assertEqual(session.steam_id, "76561198000000000")
        self.assertEqual(session.owned_app_ids, frozenset({10}))
        self.assertIn("rpg", session.preferences.preferred_tags)
        self.assertEqual(provider.resolve_calls, 1)
        self.assertEqual(provider.library_calls, 1)

    def test_private_and_rate_limited_states_are_distinct(self):
        private = _Provider(error=SteamProviderError("Steam Game Details are private or unavailable"))
        limited = _Provider(error=SteamProviderError("Steam API rate limit reached; try again later"))

        private_state = analyze_public_profile("private", private, _Catalog())
        limited_state = analyze_public_profile("limited", limited, _Catalog())

        self.assertEqual(private_state.status, "private")
        self.assertEqual(limited_state.status, "rate_limited")
        self.assertEqual(private_state.message, "Game Details are private.")
        self.assertEqual(limited_state.message, "Steam is temporarily rate limited.")

    def test_empty_session_is_disconnected(self):
        session = empty_profile_session()

        self.assertEqual(session.status, "disconnected")
        self.assertEqual(session.owned_app_ids, frozenset())
        self.assertEqual(session.profile_input, "")

    def test_blank_profile_does_not_call_provider(self):
        provider = _Provider()

        session = analyze_public_profile("  ", provider, _Catalog())

        self.assertEqual(session.status, "disconnected")
        self.assertEqual(provider.resolve_calls, 0)
        self.assertEqual(provider.library_calls, 0)


if __name__ == "__main__":
    unittest.main()

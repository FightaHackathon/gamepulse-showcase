import unittest
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from gamepulse.providers.steam import SteamProvider, SteamProviderError, parse_steam_profile


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class _TextResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload.encode("utf-8")


PUBLIC_PROFILE_HTML = """
<script>
g_rgProfileData = {"url":"https:\/\/steamcommunity.com\/profiles\/76561199124746372\/","steamid":"76561199124746372"};
</script>
<div class="recent_games">
  <div class="recent_game">
    <div class="game_info_details">12.5 hrs on record<br>last played today</div>
    <div class="game_name"><a href="https://steamcommunity.com/app/570">Dota 2</a></div>
  </div>
  <div class="recent_game">
    <div class="game_info_details">2 hrs on record<br>last played yesterday</div>
    <div class="game_name"><a href="https://steamcommunity.com/app/1149460">Icarus</a></div>
  </div>
</div>
"""


PUBLIC_GAMES_HTML = """
<div class="gameList">
  <div class="gameListRow" data-appid="570">
    <div class="gameListRowItemName ellipsis">Dota 2</div>
    <div class="gameListRowItem">
      <div class="gameListRowItemLabel">PLAYTIME</div>
      <div class="gameListRowItemValue">12.5 hrs on record</div>
    </div>
  </div>
  <div class="gameListRow" data-appid="1149460">
    <div class="gameListRowItemName ellipsis">Icarus</div>
    <div class="gameListRowItem">
      <div class="gameListRowItemLabel">PLAYTIME</div>
      <div class="gameListRowItemValue">2 hrs on record</div>
    </div>
  </div>
</div>
"""


class SteamProviderTests(unittest.TestCase):
    def test_parse_numeric_profile_and_vanity_profile(self):
        self.assertEqual(parse_steam_profile("https://steamcommunity.com/profiles/76561198000000000"), ("76561198000000000", None))
        self.assertEqual(parse_steam_profile("https://steamcommunity.com/profiles/76561199124746372/?tab=all"), ("76561199124746372", None))
        self.assertEqual(parse_steam_profile("https://steamcommunity.com/id/example"), (None, "example"))

    def test_reject_malformed_profile(self):
        with self.assertRaises(ValueError):
            parse_steam_profile("not-a-steam-profile")

    def test_rejects_foreign_or_malformed_profile_urls(self):
        for value in (
            "https://example.com/id/example",
            "https://steamcommunity.com/id/example/extra",
            "https://steamcommunity.com/profiles/not-a-steamid",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "steamcommunity.com|17-digit"):
                    parse_steam_profile(value)

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_keyless_vanity_profile_resolves_then_reads_public_games(self, urlopen):
        urlopen.side_effect = [
            _TextResponse(PUBLIC_PROFILE_HTML),
            _TextResponse(PUBLIC_PROFILE_HTML),
            _TextResponse(PUBLIC_GAMES_HTML),
        ]

        provider = SteamProvider(None)
        self.assertEqual(provider.resolve_profile("https://steamcommunity.com/id/example/"), "76561199124746372")
        library = provider.get_library("76561199124746372")

        self.assertEqual([item["appid"] for item in library.games], [570, 1149460])
        self.assertEqual([item["name"] for item in library.games], ["Dota 2", "Icarus"])

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_keyless_private_games_raise_actionable_error(self, urlopen):
        private_games = """
        <html><body><div class="profile_private_info">This profile is private.</div></body></html>
        """
        urlopen.side_effect = [_TextResponse(PUBLIC_PROFILE_HTML), _TextResponse(private_games)]

        with self.assertRaisesRegex(SteamProviderError, "private|public"):
            SteamProvider(None).get_library("76561199124746372")

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_keyless_network_failure_is_recoverable(self, urlopen):
        urlopen.side_effect = URLError("offline")

        with self.assertRaisesRegex(SteamProviderError, "unavailable|connection|try again"):
            SteamProvider(None).get_library("76561199124746372")

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_keyless_games_tab_failure_falls_back_to_public_recent_games(self, urlopen):
        urlopen.side_effect = [
            _TextResponse(PUBLIC_PROFILE_HTML),
            URLError("games tab unavailable"),
        ]

        library = SteamProvider(None).get_library("76561199124746372")

        self.assertEqual(library.source_name, "Public Steam profile page")
        self.assertEqual([item["appid"] for item in library.games], [570, 1149460])

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_keyless_rate_limit_is_recoverable(self, urlopen):
        urlopen.side_effect = HTTPError("https://steamcommunity.com", 429, "rate limited", {}, None)

        with self.assertRaisesRegex(SteamProviderError, "rate limit"):
            SteamProvider(None).get_library("76561199124746372")

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_public_library_is_returned_without_persisting_credentials(self, urlopen):
        urlopen.return_value = _Response({"response": {"games": [{"appid": 10, "playtime_forever": 120}]}})

        library = SteamProvider("test-key").get_library("76561198000000000")

        self.assertEqual(library.steam_id, "76561198000000000")
        self.assertEqual(library.games[0]["appid"], 10)
        self.assertTrue(library.complete)
        self.assertNotIn("test-key", repr(library))

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_private_library_is_reported_as_a_recoverable_provider_error(self, urlopen):
        urlopen.return_value = _Response({"response": {}})

        with self.assertRaisesRegex(SteamProviderError, "private"):
            SteamProvider("test-key").get_library("76561198000000000")

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_malformed_api_library_response_is_recoverable(self, urlopen):
        urlopen.return_value = _Response({"response": {"games": {"appid": 10}}})

        with self.assertRaisesRegex(SteamProviderError, "invalid"):
            SteamProvider("test-key").get_library("76561198000000000")

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_rate_limit_is_reported_without_leaking_request_details(self, urlopen):
        urlopen.side_effect = HTTPError("https://api.steampowered.com", 429, "rate limited", {}, None)

        with self.assertRaisesRegex(SteamProviderError, "rate limit"):
            SteamProvider("test-key").get_library("76561198000000000")

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_public_profile_page_fallback_analyzes_recent_games_without_api_key(self, urlopen):
        urlopen.return_value = _TextResponse(PUBLIC_PROFILE_HTML)

        library = SteamProvider(None).get_library("76561199124746372")

        self.assertEqual(library.steam_id, "76561199124746372")
        self.assertEqual(library.source_name, "Public Steam profile page")
        self.assertEqual([item["appid"] for item in library.games], [570, 1149460])
        self.assertEqual(library.games[0]["playtime_forever"], 750)

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_public_games_page_reads_all_visible_owned_games_and_playtime_without_api_key(self, urlopen):
        urlopen.side_effect = [_TextResponse(PUBLIC_PROFILE_HTML), _TextResponse(PUBLIC_GAMES_HTML)]

        library = SteamProvider(None).get_library("76561199124746372")

        self.assertEqual(library.source_name, "Public Steam games page")
        self.assertTrue(library.complete)
        self.assertEqual([item["appid"] for item in library.games], [570, 1149460])
        self.assertEqual([item["playtime_forever"] for item in library.games], [750, 120])


if __name__ == "__main__":
    unittest.main()

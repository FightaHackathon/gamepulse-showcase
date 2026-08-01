import unittest
import json
from unittest.mock import patch
from urllib.error import HTTPError

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


class SteamProviderTests(unittest.TestCase):
    def test_parse_numeric_profile_and_vanity_profile(self):
        self.assertEqual(parse_steam_profile("https://steamcommunity.com/profiles/76561198000000000"), ("76561198000000000", None))
        self.assertEqual(parse_steam_profile("https://steamcommunity.com/id/example"), (None, "example"))

    def test_reject_malformed_profile(self):
        with self.assertRaises(ValueError):
            parse_steam_profile("not-a-steam-profile")

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_public_library_is_returned_without_persisting_credentials(self, urlopen):
        urlopen.return_value = _Response({"response": {"games": [{"appid": 10, "playtime_forever": 120}]}})

        library = SteamProvider("test-key").get_library("76561198000000000")

        self.assertEqual(library.steam_id, "76561198000000000")
        self.assertEqual(library.games[0]["appid"], 10)
        self.assertNotIn("test-key", repr(library))

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_private_library_is_reported_as_a_recoverable_provider_error(self, urlopen):
        urlopen.return_value = _Response({"response": {}})

        with self.assertRaisesRegex(SteamProviderError, "private"):
            SteamProvider("test-key").get_library("76561198000000000")

    @patch("gamepulse.providers.steam.urllib.request.urlopen")
    def test_rate_limit_is_reported_without_leaking_request_details(self, urlopen):
        urlopen.side_effect = HTTPError("https://api.steampowered.com", 429, "rate limited", {}, None)

        with self.assertRaisesRegex(SteamProviderError, "rate limit"):
            SteamProvider("test-key").get_library("76561198000000000")


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from gamepulse.providers.steamspy import SteamSpyProvider


class SteamSpyProviderTests(unittest.TestCase):
    def test_fetches_app_detail_and_parses_owner_interval(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return {"appid": 570, "name": "Dota 2", "owners": "20,000 .. 50,000"}

        result = SteamSpyProvider(fetch_json=fetch).get_app_estimate(570)

        self.assertEqual(result.owners_low, 20_000)
        self.assertEqual(result.owners_high, 50_000)
        self.assertLessEqual(result.owners_low, result.owners_high)
        self.assertEqual(result.source_name, "SteamSpy appdetails API")
        self.assertEqual(result.confidence, "estimate")
        self.assertIn("not verified sales", result.caveat.lower())
        self.assertIn("request=appdetails", calls[0])
        self.assertIn("appid=570", calls[0])

    def test_parses_single_owner_value_as_bounded_interval(self):
        result = SteamSpyProvider(fetch_json=lambda _url: {"owners": "1,234"}).get_app_estimate(10)

        self.assertEqual((result.owners_low, result.owners_high), (1234, 1234))

    def test_malformed_payload_returns_actionable_unavailable_result(self):
        result = SteamSpyProvider(fetch_json=lambda _url: {"name": "No owners"}).get_app_estimate(10)

        self.assertIsNone(result.owners_low)
        self.assertIsNone(result.owners_high)
        self.assertEqual(result.confidence, "unavailable")
        self.assertIn("owners", result.error.lower())

    def test_fresh_cache_avoids_network_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "steamspy.json"
            cache_path.write_text(json.dumps({
                "version": 1,
                "entries": {
                    "app:10": {
                        "stored_at": 1000,
                        "payload": {"appid": 10, "owners": "100 .. 200"},
                    }
                },
            }), encoding="utf-8")
            calls = []
            provider = SteamSpyProvider(
                fetch_json=lambda _url: calls.append(True),
                cache_path=cache_path,
                clock=lambda: 1001,
            )

            result = provider.get_app_estimate(10)

        self.assertEqual(calls, [])
        self.assertEqual((result.owners_low, result.owners_high), (100, 200))
        self.assertEqual(result.confidence, "cached")

    def test_stale_cache_is_used_when_network_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "steamspy.json"
            cache_path.write_text(json.dumps({
                "version": 1,
                "entries": {
                    "app:10": {
                        "stored_at": 1000,
                        "payload": {"appid": 10, "owners": "300 .. 400"},
                    }
                },
            }), encoding="utf-8")
            provider = SteamSpyProvider(
                fetch_json=lambda _url: (_ for _ in ()).throw(OSError("offline")),
                cache_path=cache_path,
                clock=lambda: 1000 + 86400 + 1,
            )

            result = provider.get_app_estimate(10)

        self.assertEqual((result.owners_low, result.owners_high), (300, 400))
        self.assertEqual(result.confidence, "stale-fallback")
        self.assertIn("stale", result.caveat.lower())


if __name__ == "__main__":
    unittest.main()

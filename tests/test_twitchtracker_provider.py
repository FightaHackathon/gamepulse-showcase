import json
import tempfile
import unittest
from pathlib import Path

from gamepulse.providers.twitchtracker import TwitchTrackerProvider


class TwitchTrackerProviderTests(unittest.TestCase):
    def test_fetches_and_normalizes_documented_game_summary(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return {
                "game": {"id": 509658, "name": "Just Chatting"},
                "viewers": 123456,
                "channels": 789,
                "average_viewers": 120000,
                "peak_viewers": 150000,
            }

        result = TwitchTrackerProvider(fetch_json=fetch).get_game_summary("509658")

        self.assertEqual(result.game_id, "509658")
        self.assertEqual(result.game_name, "Just Chatting")
        self.assertEqual(result.viewer_count, 123456)
        self.assertEqual(result.channel_count, 789)
        self.assertEqual(result.average_viewers, 120000)
        self.assertEqual(result.peak_viewers, 150000)
        self.assertEqual(result.source_name, "TwitchTracker API")
        self.assertTrue(result.observed_at)
        self.assertEqual(result.confidence, "live")
        self.assertIsNone(result.error)
        self.assertIn("509658", calls[0])

    def test_malformed_payload_returns_actionable_unavailable_result(self):
        result = TwitchTrackerProvider(fetch_json=lambda _url: {"game": {"name": "Missing metrics"}}).get_game_summary("123")

        self.assertIsNone(result.viewer_count)
        self.assertIsNone(result.channel_count)
        self.assertEqual(result.confidence, "unavailable")
        self.assertIn("metrics", result.error.lower())

    def test_empty_payload_returns_actionable_unavailable_result(self):
        result = TwitchTrackerProvider(fetch_json=lambda _url: {}).get_game_summary("123")

        self.assertEqual(result.confidence, "unavailable")
        self.assertIn("no usable", result.error.lower())

    def test_fresh_cache_avoids_network_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "twitchtracker.json"
            cache_path.write_text(json.dumps({
                "version": 1,
                "entries": {
                    "game:123": {
                        "stored_at": 1000,
                        "payload": {"game": {"id": 123, "name": "Cached"}, "viewers": 10, "channels": 2},
                    }
                },
            }), encoding="utf-8")
            calls = []
            provider = TwitchTrackerProvider(
                fetch_json=lambda _url: calls.append(True),
                cache_path=cache_path,
                clock=lambda: 1001,
            )

            result = provider.get_game_summary("123")

        self.assertEqual(calls, [])
        self.assertEqual(result.viewer_count, 10)
        self.assertEqual(result.channel_count, 2)
        self.assertEqual(result.confidence, "cached")
        self.assertIn("cache", result.caveat.lower())

    def test_stale_cache_is_used_when_network_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "twitchtracker.json"
            cache_path.write_text(json.dumps({
                "version": 1,
                "entries": {
                    "game:123": {
                        "stored_at": 1000,
                        "payload": {"game": {"id": 123, "name": "Stale"}, "viewers": 20, "channels": 3},
                    }
                },
            }), encoding="utf-8")
            provider = TwitchTrackerProvider(
                fetch_json=lambda _url: (_ for _ in ()).throw(OSError("offline")),
                cache_path=cache_path,
                clock=lambda: 1000 + 86400 + 1,
            )

            result = provider.get_game_summary("123")

        self.assertEqual(result.viewer_count, 20)
        self.assertEqual(result.confidence, "stale-fallback")
        self.assertIn("stale", result.caveat.lower())
        self.assertIn("network", result.caveat.lower())


if __name__ == "__main__":
    unittest.main()

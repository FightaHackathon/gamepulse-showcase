import json
import tempfile
import unittest
from pathlib import Path

from gamepulse.providers.twitch import TwitchProvider
from gamepulse.providers.twitch_snapshot import import_snapshot


class TwitchProviderTests(unittest.TestCase):
    def test_demo_provider_returns_provenance_and_observations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = Path(temp_dir) / "snapshot.json"
            snapshot.write_text(json.dumps({
                "observed_at": "2026-08-01T00:00:00Z",
                "source_name": "test fixture",
                "games": [{"game_id": "g1", "name": "Example", "viewer_count": 100, "channel_count": 5}],
                "streamers": [{"streamer_id": "s1", "name": "ExampleStreamer", "game_id": "g1", "game_name": "Example", "viewer_count": 100, "language": "en", "channel_size_tier": "emerging"}],
            }), encoding="utf-8")
            provider = TwitchProvider(snapshot_path=snapshot)
            trends = provider.get_game_trends()
            streamers = provider.get_streamers("g1")

        self.assertEqual(trends.mode, "Demo")
        self.assertEqual(trends.data[0].viewer_count, 100)
        self.assertEqual(streamers.data[0].streamer_id, "s1")

    def test_authorized_snapshot_import_validates_and_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.json"
            destination = Path(temp_dir) / "nested" / "snapshot.json"
            source.write_text(json.dumps({
                "observed_at": "2026-08-01T00:00:00Z",
                "source_name": "authorized export",
                "games": [{"game_id": "g1", "name": "Example"}],
                "streamers": [{"streamer_id": "s1", "name": "Creator", "game_id": "g1", "game_name": "Example"}],
            }), encoding="utf-8")
            import_snapshot(source, destination)
            provider = TwitchProvider(destination)
            self.assertEqual(provider.get_game_trends().source_name, "authorized export")

    def test_live_game_trends_aggregate_stream_viewers_and_channels(self):
        provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"), "client", "secret")

        def request(url, _params):
            if url.endswith("/games/top"):
                return {"data": [{"id": "twitch-1", "name": "Example"}, {"id": "twitch-2", "name": "Other"}]}
            return {"data": [
                {"user_id": "u1", "game_id": "twitch-1", "game_name": "Example", "viewer_count": 100},
                {"user_id": "u2", "game_id": "twitch-1", "game_name": "Example", "viewer_count": 40},
                {"user_id": "u3", "game_id": "twitch-2", "game_name": "Other", "viewer_count": 20},
            ]}

        provider._request_json = request

        snapshot = provider.get_game_trends()

        self.assertEqual(snapshot.data[0].viewer_count, 140)
        self.assertEqual(snapshot.data[0].channel_count, 2)
        self.assertEqual(snapshot.data[1].viewer_count, 20)
        self.assertIn("bounded", snapshot.source_name.lower())

    def test_live_game_trends_fall_back_to_cached_snapshot_when_twitch_is_unavailable(self):
        provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"), "client", "secret")
        provider._request_json = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline"))

        snapshot = provider.get_game_trends()

        self.assertEqual(snapshot.mode, "Fallback")
        self.assertEqual(snapshot.data[0].viewer_count, 98000)

    def test_live_streamers_fall_back_to_cached_category_when_twitch_is_unavailable(self):
        provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"), "client", "secret")
        provider._request_json = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline"))

        snapshot = provider.get_streamers("10")

        self.assertEqual(snapshot.mode, "Fallback")
        self.assertEqual(snapshot.data[0].name, "DemoClassicFPSCreator")


if __name__ == "__main__":
    unittest.main()

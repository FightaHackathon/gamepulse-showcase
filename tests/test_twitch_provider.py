import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from gamepulse.providers.twitch import TwitchProvider
from gamepulse.providers.twitch_snapshot import import_snapshot


class _JsonResponse:
    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = headers or {}

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class TwitchProviderTests(unittest.TestCase):
    def test_live_game_trends_collect_bounded_pages_and_derive_observed_metrics(self):
        provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"), "client", "secret", max_stream_pages=2)
        calls = []

        def request(url, params):
            calls.append((url, dict(params)))
            if url.endswith("/games/top"):
                return {"data": [{"id": "g1", "name": "Example"}]}
            if params.get("after") == "cursor-1":
                return {
                    "data": [
                        {"id": "stream-2", "user_id": "u2", "game_id": "g1", "game_name": "Example", "viewer_count": 300, "language": "fr", "started_at": "2026-08-01T11:00:00Z"},
                        {"id": "stream-3", "user_id": "u3", "game_id": "g1", "game_name": "Example", "viewer_count": 100, "language": "en", "started_at": "2026-08-01T11:00:00Z"},
                    ],
                    "pagination": {"cursor": "cursor-2"},
                }
            return {
                "data": [
                    {"id": "stream-1", "user_id": "u1", "game_id": "g1", "game_name": "Example", "viewer_count": 600, "language": "en", "started_at": "2026-08-01T10:00:00Z"},
                    {"id": "stream-1", "user_id": "u1", "game_id": "g1", "game_name": "Example", "viewer_count": 600, "language": "en", "started_at": "2026-08-01T10:00:00Z"},
                ],
                "pagination": {"cursor": "cursor-1"},
            }

        provider._request_json = request

        observation_time = datetime(2026, 8, 1, 12, tzinfo=timezone.utc).timestamp()
        with patch("gamepulse.providers.twitch.time.time", return_value=observation_time):
            snapshot = provider.get_game_trends()
        trend = snapshot.data[0]

        self.assertEqual([params.get("after") for url, params in calls if url.endswith("/streams")], [None, "cursor-1"])
        self.assertEqual(trend.viewer_count, 1000)
        self.assertEqual(trend.channel_count, 3)
        self.assertEqual(trend.rank, 1)
        self.assertEqual(trend.viewer_to_channel, 1000 / 3)
        self.assertAlmostEqual(trend.top_one_viewer_share, 0.6)
        self.assertAlmostEqual(trend.top_five_viewer_share, 1.0)
        self.assertEqual(trend.contributing_stream_rows, 3)
        self.assertEqual(trend.pages_collected, 2)
        self.assertTrue(trend.partial_coverage)
        self.assertTrue(trend.observed_total)
        self.assertEqual(trend.language_distribution, (("en", 2), ("fr", 1)))
        self.assertAlmostEqual(trend.average_observed_stream_age_seconds, 4800.0)

    def test_empty_page_stops_cursor_pagination_without_marking_partial(self):
        provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"), "client", "secret", max_stream_pages=3)
        stream_calls = []

        def request(url, params):
            if url.endswith("/games/top"):
                return {"data": [{"id": "g1", "name": "Example"}]}
            stream_calls.append(dict(params))
            if len(stream_calls) == 1:
                return {"data": [{"id": "stream-1", "user_id": "u1", "game_id": "g1", "viewer_count": 10}], "pagination": {"cursor": "next"}}
            return {"data": [], "pagination": {"cursor": "ignored"}}

        provider._request_json = request

        trend = provider.get_game_trends().data[0]

        self.assertEqual(len(stream_calls), 2)
        self.assertEqual(stream_calls[1]["after"], "next")
        self.assertEqual(trend.pages_collected, 2)
        self.assertFalse(trend.partial_coverage)

    def test_low_remaining_capacity_skips_optional_stream_collection(self):
        provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"), "client", "secret")
        calls = []

        def request(url, params):
            calls.append(url)
            if url.endswith("/games/top"):
                provider._rate_limit_remaining = 1
                return {"data": [{"id": "g1", "name": "Example"}]}
            raise AssertionError("optional streams request should be skipped at low capacity")

        provider._request_json = request

        trend = provider.get_game_trends().data[0]

        self.assertEqual(calls, ["https://api.twitch.tv/helix/games/top"])
        self.assertTrue(trend.partial_coverage)
        self.assertEqual(trend.pages_collected, 0)
        self.assertFalse(trend.observed_total)

    def test_live_streamers_keep_optional_fields_and_assign_category_rank(self):
        provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"), "client", "secret")

        def request(url, _params):
            if url.endswith("/users"):
                return {"data": []}
            return {
                "data": [{
                    "user_id": "u1",
                    "user_name": "Creator",
                    "game_id": "g1",
                    "game_name": "Example",
                    "viewer_count": 40,
                }],
                "pagination": {},
            }

        provider._request_json = request

        observation = provider.get_streamers("g1").data[0]

        self.assertEqual(observation.streamer_id, "u1")
        self.assertIsNone(observation.stream_id)
        self.assertIsNone(observation.login_name)
        self.assertIsNone(observation.stream_title)
        self.assertIsNone(observation.start_time)
        self.assertIsNone(observation.thumbnail_url)
        self.assertIsNone(observation.broadcaster_type)
        self.assertIsNone(observation.profile_image_url)
        self.assertEqual(observation.category_rank, 1)

    def test_live_streamers_follow_cursors_deduplicate_and_enrich_profiles(self):
        provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"), "client", "secret", max_stream_pages=2)

        def request(url, params):
            if url.endswith("/users"):
                return {"data": [{
                    "id": "u1",
                    "login": "creator_login",
                    "display_name": "Creator Display",
                    "broadcaster_type": "affiliate",
                    "profile_image_url": "https://example.test/profile.png",
                }]}
            if params.get("after") == "cursor-1":
                return {"data": [{
                    "id": "stream-2",
                    "user_id": "u1",
                    "user_name": "Creator",
                    "user_login": "creator_login",
                    "game_id": "g1",
                    "game_name": "Example",
                    "viewer_count": 20,
                    "language": "en",
                }], "pagination": {}}
            return {"data": [{
                "id": "stream-1",
                "user_id": "u1",
                "user_name": "Creator",
                "user_login": "creator_login",
                "game_id": "g1",
                "game_name": "Example",
                "viewer_count": 40,
                "language": "en",
                "title": "A stream title",
                "started_at": "2026-08-01T11:00:00Z",
                "thumbnail_url": "https://example.test/thumb.jpg",
                "tags": ["FPS"],
            }, {
                "id": "stream-1",
                "user_id": "u1",
                "user_name": "Creator",
                "game_id": "g1",
                "game_name": "Example",
                "viewer_count": 40,
                "language": "en",
            }], "pagination": {"cursor": "cursor-1"}}

        provider._request_json = request

        observations = provider.get_streamers("g1").data

        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0].stream_id, "stream-1")
        self.assertEqual(observations[0].login_name, "creator_login")
        self.assertEqual(observations[0].stream_title, "A stream title")
        self.assertEqual(observations[0].started_at, "2026-08-01T11:00:00Z")
        self.assertEqual(observations[0].thumbnail_url, "https://example.test/thumb.jpg")
        self.assertEqual(observations[0].broadcaster_type, "affiliate")
        self.assertEqual(observations[0].profile_image_url, "https://example.test/profile.png")
        self.assertEqual(observations[0].category_rank, 1)
        self.assertEqual(observations[1].category_rank, 2)

    def test_response_headers_are_recorded_and_rate_limit_429_falls_back(self):
        provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"), "client", "secret")
        provider._access_token = "cached-token"
        provider._token_expires_at = time.time() + 3600
        rate_limited = HTTPError(
            "https://api.twitch.tv/helix/games/top",
            429,
            "rate limited",
            {"Ratelimit-Remaining": "0", "Ratelimit-Limit": "800", "Ratelimit-Reset": "123"},
            None,
        )

        with patch("gamepulse.providers.twitch.urllib.request.urlopen", side_effect=rate_limited):
            snapshot = provider.get_game_trends()

        self.assertEqual(snapshot.mode, "Fallback")
        self.assertEqual(provider.rate_limit_remaining, 0)
        self.assertEqual(provider.rate_limit_limit, 800)
        self.assertEqual(provider.rate_limit_reset, 123)

    def test_token_is_reused_across_live_requests(self):
        provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"), "client", "secret")
        provider._access_token = "cached-token"
        provider._token_expires_at = time.time() + 3600
        responses = [
            _JsonResponse({"data": [{"id": "g1", "name": "Example"}]}),
            _JsonResponse({"data": [{"id": "stream-1", "user_id": "u1", "game_id": "g1", "viewer_count": 10}], "pagination": {}}),
        ]

        with patch("gamepulse.providers.twitch.urllib.request.urlopen", side_effect=responses) as urlopen:
            snapshot = provider.get_game_trends()

        self.assertEqual(snapshot.mode, "Live")
        self.assertEqual(urlopen.call_count, 2)
        for call in urlopen.call_args_list:
            self.assertEqual(call.args[0].headers["Authorization"], "Bearer cached-token")

    def test_one_401_refreshes_token_and_retries_once(self):
        provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"), "client", "secret")
        unauthorized = HTTPError("https://api.twitch.tv/helix/games/top", 401, "expired", {}, None)
        responses = [
            _JsonResponse({"access_token": "expired-token", "expires_in": 3600}),
            unauthorized,
            _JsonResponse({"access_token": "refreshed-token", "expires_in": 3600}),
            _JsonResponse({"data": [{"id": "g1", "name": "Example"}]}),
            _JsonResponse({"data": [{"id": "stream-1", "user_id": "u1", "game_id": "g1", "viewer_count": 10}], "pagination": {}}),
        ]

        with patch("gamepulse.providers.twitch.urllib.request.urlopen", side_effect=responses) as urlopen:
            snapshot = provider.get_game_trends()

        self.assertEqual(snapshot.mode, "Live")
        self.assertEqual(urlopen.call_count, 5)
        self.assertEqual(urlopen.call_args_list[3].args[0].headers["Authorization"], "Bearer refreshed-token")

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

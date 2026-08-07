import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gamepulse.database import initialize_schema
from gamepulse.providers.composite import CompositeSignalProvider
from gamepulse.providers.creator_directory import CreatorDirectoryError, CreatorDirectoryProvider
from gamepulse.providers.snapshot import normalize_snapshot
from gamepulse.providers.steam_signals import SteamPublicGameSignalProvider
from gamepulse.providers.twitch import TwitchProvider


class SourceNeutralProviderTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        path = root / "gamepulse.sqlite3"
        connection = sqlite3.connect(path)
        initialize_schema(connection)
        connection.execute(
            """INSERT INTO games (
                   steam_app_id, name, peak_ccu, review_score, discount_pct,
                   positive_reviews, negative_reviews, total_reviews, windows, mac, linux
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (10, "Example Game", 5000, 0.9, 20, 90, 10, 100, 1, 0, 0),
        )
        connection.execute("INSERT INTO game_tags VALUES (?, ?)", (10, "FPS"))
        connection.execute("INSERT INTO game_genres VALUES (?, ?)", (10, "Action"))
        latest = 1_800_000_000
        for index in range(8):
            created_at = latest - index * 2 * 24 * 60 * 60
            connection.execute(
                "INSERT INTO reviews (review_id, steam_app_id, review_text, created_at_unix) VALUES (?, ?, ?, ?)",
                (f"recent-{index}", 10, "good", created_at),
            )
        for index in range(2):
            created_at = latest - 35 * 24 * 60 * 60 - index * 2 * 24 * 60 * 60
            connection.execute(
                "INSERT INTO reviews (review_id, steam_app_id, review_text, created_at_unix) VALUES (?, ?, ?, ?)",
                (f"prior-{index}", 10, "older", created_at),
            )
        connection.execute(
            """INSERT INTO steam_market_snapshots (
                   observed_at, steam_app_id, peak_ccu, player_metric, source_mode,
                   source_name, confidence
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "2026-08-07T00:00:00Z",
                10,
                4200,
                "current",
                "Live",
                "Steam public endpoint snapshot",
                "public",
            ),
        )
        connection.commit()
        connection.close()
        return path

    def _creator_directory(self, root: Path) -> Path:
        creators = root / "creators.csv"
        creators.write_text(
            "creator_id,name,platform,profile_url,language,avg_viewers,channel_size_tier,tags,games,observed_at,source,confidence\n"
            "c1,Example Creator,YouTube,,en,320,emerging,FPS,Example Game,2026-08-07T00:00:00Z,manual,manual\n",
            encoding="utf-8",
        )
        return creators

    def _generic_snapshot(self, root: Path) -> Path:
        path = root / "snapshot.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "observed_at": "2026-08-07T00:00:00Z",
                    "source_name": "imported fixture",
                    "source_mode": "Imported",
                    "games": [],
                    "creators": [
                        {
                            "creator_id": "imported-1",
                            "name": "Imported Creator",
                            "platform": "YouTube",
                            "game_id": None,
                            "game_name": None,
                            "audience_value": 450,
                            "audience_metric": "avg_viewers",
                            "language": "en",
                            "channel_size_tier": "emerging",
                            "tags": ["FPS"],
                            "games": ["Example Game"],
                            "source_mode": "Imported",
                            "source_name": "imported fixture",
                            "confidence": "imported",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_steam_provider_works_without_twitch_credentials(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = SteamPublicGameSignalProvider(
                self._database(Path(temp_dir))
            ).get_game_trends()

        self.assertEqual(snapshot.mode, "Prepared")
        self.assertEqual(snapshot.data[0].audience_metric, "steam_current_players")
        self.assertEqual(snapshot.data[0].audience_value, 4200)
        self.assertIsNone(snapshot.data[0].competition_value)
        self.assertGreater(snapshot.data[0].growth_score, 0.5)
        self.assertIn("FPS", snapshot.data[0].tags)

    def test_creator_directory_parses_pipe_delimited_fields_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "creators.csv"
            path.write_text(
                "creator_id,name,platform,profile_url,language,avg_viewers,channel_size_tier,tags,games,observed_at,source,confidence\n"
                "c1,Example Creator,YouTube,,en,320,emerging,FPS|Indie,Example Game|Other,2026-08-07T00:00:00Z,creator_submitted,creator_submitted\n",
                encoding="utf-8",
            )
            result = CreatorDirectoryProvider(path).get_creators(
                game_name="Example Game"
            )

        self.assertEqual(result.data[0].tags, ("FPS", "Indie"))
        self.assertEqual(result.data[0].games, ("Example Game", "Other"))
        self.assertEqual(result.data[0].source_mode, "Creator submitted")
        self.assertEqual(result.data[0].audience_metric, "avg_viewers")

    def test_invalid_creator_row_fails_with_row_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "creators.csv"
            path.write_text(
                "creator_id,name,platform,profile_url,language,avg_viewers,channel_size_tier,tags,games,observed_at,source,confidence\n"
                "c1,Bad Creator,YouTube,,en,not-a-number,emerging,FPS,Example Game,2026-08-07T00:00:00Z,manual,low\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CreatorDirectoryError, "row 2"):
                CreatorDirectoryProvider(path).get_creators()

    def test_schema_v2_preserves_null_competition_and_metric_identity(self):
        payload = {
            "schema_version": 2,
            "observed_at": "2026-08-07T00:00:00Z",
            "source_name": "test snapshot",
            "source_mode": "Imported",
            "games": [
                {
                    "game_id": "10",
                    "name": "Example",
                    "audience_value": 1000,
                    "audience_metric": "steam_current_players",
                    "competition_value": None,
                    "competition_metric": None,
                    "growth_score": 0.6,
                    "tags": ["FPS"],
                    "platform": "Steam",
                }
            ],
            "creators": [],
        }

        result = normalize_snapshot(payload)

        self.assertIsNone(result.games.data[0].competition_value)
        self.assertEqual(result.games.data[0].audience_metric, "steam_current_players")

    def test_legacy_twitch_snapshot_remains_compatible(self):
        payload = {
            "observed_at": "2026-08-01T00:00:00Z",
            "source_name": "legacy fixture",
            "games": [
                {
                    "game_id": "g1",
                    "name": "Example",
                    "viewer_count": 100,
                    "channel_count": 5,
                }
            ],
            "streamers": [
                {
                    "streamer_id": "s1",
                    "name": "Creator",
                    "game_id": "g1",
                    "game_name": "Example",
                }
            ],
        }

        result = normalize_snapshot(payload)

        self.assertEqual(result.games.data[0].audience_metric, "twitch_viewers")
        self.assertEqual(
            result.games.data[0].competition_metric, "twitch_live_channels"
        )
        self.assertEqual(result.creators.data[0].creator_id, "s1")

    def test_composite_auto_prefers_prepared_steam_and_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            provider = CompositeSignalProvider(
                database_path=self._database(root),
                creator_directory_path=self._creator_directory(root),
            )

            games = provider.get_game_trends()
            creator_snapshot = provider.get_creators(game_name="Example Game")

        self.assertEqual(games.data[0].platform, "Steam")
        self.assertEqual(creator_snapshot.data[0].name, "Example Creator")

    def test_directory_mode_does_not_silently_merge_imported_creators(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            provider = CompositeSignalProvider(
                database_path=self._database(root),
                creator_directory_path=self._creator_directory(root),
                snapshot_path=self._generic_snapshot(root),
                creator_provider_mode="directory",
            )

            creators = provider.get_creators(game_name="Example Game").data

        self.assertEqual([item.name for item in creators], ["Example Creator"])

    def test_auto_mode_can_merge_directory_and_imported_creators(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            provider = CompositeSignalProvider(
                database_path=self._database(root),
                creator_directory_path=self._creator_directory(root),
                snapshot_path=self._generic_snapshot(root),
                creator_provider_mode="auto",
            )

            creators = provider.get_creators(game_name="Example Game").data

        self.assertEqual(
            {item.name for item in creators},
            {"Example Creator", "Imported Creator"},
        )

    def test_missing_twitch_credentials_load_snapshot_without_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "snapshot.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "observed_at": "2026-08-07T00:00:00Z",
                        "source_name": "demo",
                        "source_mode": "Demo",
                        "games": [
                            {
                                "game_id": "10",
                                "name": "Example",
                                "audience_value": 100,
                                "audience_metric": "steam_current_players",
                                "competition_value": None,
                                "competition_metric": None,
                                "growth_score": 0.5,
                                "tags": [],
                                "platform": "Steam",
                            }
                        ],
                        "creators": [],
                    }
                ),
                encoding="utf-8",
            )

            snapshot = TwitchProvider(path).get_game_trends()

        self.assertEqual(snapshot.mode, "Demo")
        self.assertEqual(snapshot.data[0].audience_metric, "steam_current_players")


if __name__ == "__main__":
    unittest.main()

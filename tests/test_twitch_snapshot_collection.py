import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gamepulse.database import SCHEMA, initialize_schema
from gamepulse.providers.twitch import GameTrend, Snapshot, StreamerObservation, TwitchProvider
from scripts.collect_twitch_snapshot import collect_and_save


class _FakeProvider:
    def __init__(self, partial: bool = False):
        self.partial = partial

    def get_game_trends(self):
        return Snapshot(
            "Demo",
            "2026-08-02T00:00:00Z",
            "test fixture",
            [GameTrend(
                "g1",
                "Example",
                1000,
                10,
                0.25,
                rank=1,
                viewer_to_channel=100.0,
                top_one_viewer_share=0.6,
                top_five_viewer_share=1.0,
                average_stream_age_seconds=3600.0,
                contributing_stream_rows=2,
                pages_collected=3 if self.partial else 1,
                partial_coverage=self.partial,
                observed_total=True,
            )],
        )

    def get_streamers(self, game_id: str):
        return Snapshot(
            "Demo",
            "2026-08-02T00:00:00Z",
            "test fixture",
            [StreamerObservation(
                "u1",
                "Creator",
                game_id,
                "Example",
                500,
                "en",
                "emerging",
                ("FPS", "Competitive"),
                stream_id="stream-1",
                login_name="creator_login",
                stream_title="A title",
                started_at="2026-08-01T23:00:00Z",
                broadcaster_type="affiliate",
                profile_image_url="https://example.test/profile.png",
                category_rank=1,
            )],
        )


class TwitchSnapshotCollectionTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        database = root / "gamepulse.sqlite3"
        connection = sqlite3.connect(database)
        try:
            connection.executescript(SCHEMA)
            connection.commit()
        finally:
            connection.close()
        return database

    def test_schema_contains_twitch_snapshot_fields_and_indexes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "schema.sqlite3"
            connection = sqlite3.connect(database)
            initialize_schema(connection)
            game_columns = {row[1] for row in connection.execute("PRAGMA table_info(twitch_game_snapshots)")}
            streamer_columns = {row[1] for row in connection.execute("PRAGMA table_info(twitch_streamer_snapshots)")}
            indexes = {row[1] for row in connection.execute("PRAGMA index_list(twitch_game_snapshots)")} | {row[1] for row in connection.execute("PRAGMA index_list(twitch_streamer_snapshots)")}
            connection.close()

        self.assertTrue({
            "observed_at", "game_id", "game_name", "steam_app_id", "rank", "viewer_count", "channel_count",
            "viewer_to_channel", "top_one_viewer_share", "top_five_viewer_share", "average_stream_age_seconds",
            "growth_score", "coverage_stream_count", "coverage_page_count", "partial_coverage", "source_mode", "source_name",
        } <= game_columns)
        self.assertTrue({
            "observed_at", "stream_id", "streamer_id", "streamer_name", "streamer_login", "game_id", "game_name",
            "viewer_count", "language", "title", "start_time", "tags_json", "channel_size_tier", "broadcaster_type",
            "profile_image_url", "category_rank", "source_mode", "source_name",
        } <= streamer_columns)
        self.assertTrue({
            "twitch_games_observed", "twitch_games_game_observed", "twitch_streamers_observed", "twitch_streamers_game_observed",
        } <= indexes)

    def test_snapshot_inserts_and_duplicate_safe_upserts_preserve_normalized_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = self._database(Path(temp_dir))
            first = collect_and_save(database, provider=_FakeProvider())
            second = collect_and_save(database, provider=_FakeProvider())
            connection = sqlite3.connect(database)
            try:
                game_row = connection.execute("SELECT steam_app_id, viewer_to_channel, top_one_viewer_share, coverage_stream_count FROM twitch_game_snapshots").fetchone()
                streamer_row = connection.execute("SELECT stream_id, streamer_login, title, start_time, tags_json, broadcaster_type FROM twitch_streamer_snapshots").fetchone()
                counts = connection.execute("SELECT COUNT(*), (SELECT COUNT(*) FROM twitch_streamer_snapshots) FROM twitch_game_snapshots").fetchone()
            finally:
                connection.close()

        self.assertEqual(first.categories, 1)
        self.assertEqual(second.streamers, 1)
        self.assertEqual(game_row, (None, 100.0, 0.6, 2))
        self.assertEqual(streamer_row[:4], ("stream-1", "creator_login", "A title", "2026-08-01T23:00:00Z"))
        self.assertEqual(json.loads(streamer_row[4]), ["FPS", "Competitive"])
        self.assertEqual(streamer_row[5], "affiliate")
        self.assertEqual(counts, (1, 1))

    def test_demo_provider_snapshot_can_be_imported_into_sqlite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database = self._database(root)
            provider = TwitchProvider(Path("data/demo/twitch_snapshot.json"))

            report = collect_and_save(database, provider=provider)

            connection = sqlite3.connect(database)
            try:
                game_count = connection.execute("SELECT COUNT(*) FROM twitch_game_snapshots").fetchone()[0]
                streamer_count = connection.execute("SELECT COUNT(*) FROM twitch_streamer_snapshots").fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(report.source_mode, "Demo")
        self.assertEqual(report.categories, 4)
        self.assertEqual(game_count, 4)
        self.assertEqual(streamer_count, 4)

    def test_partial_snapshot_report_and_rows_keep_coverage_flag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = self._database(Path(temp_dir))

            report = collect_and_save(database, provider=_FakeProvider(partial=True))

            connection = sqlite3.connect(database)
            try:
                row = connection.execute("SELECT coverage_page_count, partial_coverage FROM twitch_game_snapshots").fetchone()
            finally:
                connection.close()

        self.assertTrue(report.partial_coverage)
        self.assertEqual(row, (3, 1))

    def test_reliable_steam_mapping_is_written_to_game_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = self._database(Path(temp_dir))
            connection = sqlite3.connect(database)
            try:
                connection.execute("INSERT INTO games (steam_app_id, name) VALUES (?, ?)", (1, "Example"))
                connection.commit()
            finally:
                connection.close()

            collect_and_save(database, provider=_FakeProvider())

            connection = sqlite3.connect(database)
            try:
                snapshot_row = connection.execute(
                    "SELECT steam_app_id FROM twitch_game_snapshots WHERE game_id = ?", ("g1",)
                ).fetchone()
                mapping_row = connection.execute(
                    "SELECT steam_app_id, match_method, manual_verified FROM twitch_game_mappings WHERE twitch_game_id = ?",
                    ("g1",),
                ).fetchone()
            finally:
                connection.close()

        self.assertEqual(snapshot_row, (1,))
        self.assertEqual(mapping_row, (1, "exact", 0))

    def test_invalid_demo_json_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database = self._database(root)
            invalid_snapshot = root / "invalid.json"
            invalid_snapshot.write_text("{not-json", encoding="utf-8")

            with self.assertRaises(json.JSONDecodeError):
                collect_and_save(database, provider=TwitchProvider(invalid_snapshot))


if __name__ == "__main__":
    unittest.main()

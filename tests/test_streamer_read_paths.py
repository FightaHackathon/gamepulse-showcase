from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import gamepulse.ui.streamer as streamer_ui
from gamepulse.database import connect_read_only, initialize_schema


class StreamerReadPathTests(unittest.TestCase):
    def _clear_caches(self) -> None:
        for name in (
            "_cached_twitch_history",
            "_cached_twitch_history_batch",
            "_cached_steam_context",
        ):
            cached = getattr(streamer_ui, name, None)
            if cached is not None and hasattr(cached, "clear"):
                cached.clear()

    def _create_database(self, path: Path, category_count: int = 2) -> None:
        connection = sqlite3.connect(path)
        try:
            initialize_schema(connection)
            for index in range(category_count):
                game_id = f"game-{index}"
                app_id = 1000 + index
                connection.execute(
                    """
                    INSERT INTO twitch_game_mappings (
                        twitch_game_id, twitch_name, steam_app_id, steam_name,
                        match_method, match_score, manual_verified, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        game_id,
                        f"Category {index}",
                        app_id,
                        f"Steam Category {index}",
                        "exact",
                        1.0,
                        1,
                        "2026-08-01T00:00:00+00:00",
                    ),
                )
                connection.execute(
                    "INSERT INTO games (steam_app_id, name, review_score) VALUES (?, ?, ?)",
                    (app_id, f"Steam Category {index}", 90.0 + index / 10),
                )
                connection.execute(
                    "INSERT INTO game_genres (steam_app_id, value) VALUES (?, ?)",
                    (app_id, "Action"),
                )
                connection.execute(
                    "INSERT INTO game_tags (steam_app_id, value) VALUES (?, ?)",
                    (app_id, "Competitive"),
                )
                connection.execute(
                    """
                    INSERT INTO twitch_game_snapshots (
                        game_id, game_name, observed_at, viewer_count,
                        channel_count, viewer_to_channel, top_one_viewer_share,
                        top_five_viewer_share, growth_score, source_mode,
                        source_name, partial_coverage
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        game_id,
                        f"Category {index}",
                        "2026-08-01T00:00:00+00:00",
                        100 + index,
                        10,
                        10.0 + index / 10,
                        0.2,
                        0.5,
                        0.1,
                        "Live",
                        "Twitch Helix",
                        0,
                    ),
                )
            connection.commit()
        finally:
            connection.close()

    def _instrument_connections(self, original, connections, statements):
        connection = original
        connection.set_trace_callback(statements.append)
        connections.append(connection)
        return connection

    def test_one_batched_history_query_replaces_per_category_reads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "history.sqlite"
            self._create_database(path, category_count=100)
            game_ids = [f"game-{index}" for index in range(100)]

            legacy_connections = []
            legacy_statements = []
            original_connect = streamer_ui.connect_read_only
            for game_id in game_ids:
                connection = original_connect(path)
                connection.set_trace_callback(legacy_statements.append)
                legacy_connections.append(connection)
                try:
                    connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        ("twitch_game_snapshots",),
                    ).fetchone()
                    connection.execute(
                        """
                        SELECT observed_at, viewer_count, channel_count,
                               viewer_to_channel, top_one_viewer_share,
                               top_five_viewer_share, growth_score, source_mode,
                               source_name, partial_coverage
                        FROM twitch_game_snapshots
                        WHERE game_id = ?
                        ORDER BY observed_at
                        """,
                        (game_id,),
                    ).fetchall()
                finally:
                    connection.close()

            self._clear_caches()
            connections = []
            statements = []

            def counted_connect(path_value):
                return self._instrument_connections(
                    original_connect(path_value), connections, statements
                )

            with patch.object(streamer_ui, "connect_read_only", side_effect=counted_connect):
                context = streamer_ui._historical_context(
                    path,
                    [SimpleNamespace(game_id=game_id) for game_id in game_ids],
                )

            selects = [
                statement
                for statement in statements
                if statement.lstrip().upper().startswith("SELECT")
            ]
            legacy_selects = [
                statement
                for statement in legacy_statements
                if statement.lstrip().upper().startswith("SELECT")
            ]

            self.assertEqual(len(context), 100)
            self.assertEqual(len(connections), 1)
            self.assertEqual(sum("FROM twitch_game_snapshots" in statement for statement in selects), 1)
            self.assertEqual(len(selects), 1)
            self.assertEqual(len(legacy_connections), 100)
            self.assertEqual(len(legacy_selects), 200)

            first = context["game-0"]
            self.assertEqual(first.viewer_history, (100,))
            self.assertFalse(first.growth_comparison.available)

    def test_steam_metadata_is_loaded_with_bounded_batch_queries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "steam.sqlite"
            self._create_database(path, category_count=100)
            app_ids = tuple(range(1000, 1100))
            original_connect = streamer_ui.connect_read_only
            legacy_connections = []
            legacy_statements = []
            legacy_connection = original_connect(path)
            legacy_connection.set_trace_callback(legacy_statements.append)
            legacy_connections.append(legacy_connection)
            try:
                legacy_connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                    ("twitch_game_mappings",),
                ).fetchone()
                legacy_connection.execute(
                    """SELECT twitch_game_id, twitch_name, steam_app_id, steam_name,
                              match_method, match_score, manual_verified
                       FROM twitch_game_mappings"""
                ).fetchall()
                for table in ("games", "game_genres", "game_tags"):
                    legacy_connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table,),
                    ).fetchone()
                for app_id in app_ids:
                    legacy_connection.execute(
                        "SELECT name, review_score FROM games WHERE steam_app_id = ?",
                        (app_id,),
                    ).fetchone()
                    legacy_connection.execute(
                        "SELECT value FROM game_genres WHERE steam_app_id = ? ORDER BY value",
                        (app_id,),
                    ).fetchall()
                    legacy_connection.execute(
                        "SELECT value FROM game_tags WHERE steam_app_id = ? ORDER BY value",
                        (app_id,),
                    ).fetchall()
            finally:
                legacy_connection.close()

            self._clear_caches()
            connections = []
            statements = []

            def counted_connect(path_value):
                return self._instrument_connections(
                    original_connect(path_value), connections, statements
                )

            with patch.object(streamer_ui, "connect_read_only", side_effect=counted_connect):
                mappings, features, metadata = streamer_ui._cached_steam_context(str(path))

            selects = [
                statement
                for statement in statements
                if statement.lstrip().upper().startswith("SELECT")
            ]
            legacy_selects = [
                statement
                for statement in legacy_statements
                if statement.lstrip().upper().startswith("SELECT")
            ]
            self.assertEqual(len(connections), 1)
            self.assertEqual(len(selects), 4)
            self.assertEqual(len(legacy_connections), 1)
            self.assertEqual(len(legacy_selects), 305)
            self.assertEqual(len(mappings), 100)
            self.assertEqual(len(features), 100)
            self.assertEqual(len(metadata), 100)
            self.assertEqual(metadata[1000]["name"], "Steam Category 0")
            self.assertEqual(metadata[1000]["genres"], ("Action",))
            self.assertEqual(metadata[1000]["tags"], ("Competitive",))
            self.assertAlmostEqual(metadata[1099]["review_score"], 99.9)

    def test_missing_database_tables_return_empty_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "empty.sqlite"
            sqlite3.connect(path).close()
            self._clear_caches()

            self.assertEqual(
                streamer_ui._historical_context(
                    path, [SimpleNamespace(game_id="missing")]
                ),
                {},
            )
            self.assertEqual(streamer_ui._cached_steam_context(str(path)), ({}, {}, {}))

            missing_path = Path(temporary_directory) / "does-not-exist.sqlite"
            self.assertEqual(
                streamer_ui._historical_context(
                    missing_path, [SimpleNamespace(game_id="missing")]
                ),
                {},
            )
            self.assertEqual(
                streamer_ui._cached_steam_context(str(missing_path)), ({}, {}, {})
            )

    def test_read_only_connection_rejects_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "readonly.sqlite"
            self._create_database(path)
            connection = connect_read_only(path)
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    connection.execute("CREATE TABLE write_probe (id INTEGER)")
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gamepulse.database import SCHEMA, ensure_twitch_game_mapping_schema
from gamepulse.game_mapping import (
    GameMapping,
    SteamGame,
    map_twitch_game,
    persist_game_mappings,
)


class GameMappingTests(unittest.TestCase):
    def test_mapping_schema_contains_fields_and_indexes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "mapping.sqlite3"
            connection = sqlite3.connect(database)
            try:
                connection.executescript(SCHEMA)
                columns = {row[1] for row in connection.execute("PRAGMA table_info(twitch_game_mappings)")}
                indexes = {row[1] for row in connection.execute("PRAGMA index_list(twitch_game_mappings)")}
            finally:
                connection.close()

        self.assertTrue({
            "twitch_game_id", "twitch_name", "steam_app_id", "steam_name", "match_method",
            "match_score", "manual_verified", "updated_at",
        } <= columns)
        self.assertTrue({"twitch_game_mappings_steam", "twitch_game_mappings_updated"} <= indexes)

    def test_exact_match_is_reliable_without_manual_verification(self):
        mapping = map_twitch_game(
            "730",
            "Counter-Strike 2",
            [SteamGame(730, "Counter-Strike 2")],
        )

        self.assertEqual(mapping.steam_app_id, 730)
        self.assertEqual(mapping.match_method, "exact")
        self.assertEqual(mapping.match_score, 1.0)
        self.assertFalse(mapping.manual_verified)
        self.assertTrue(mapping.is_reliable)

    def test_normalization_handles_punctuation_colons_hyphens_and_trademarks(self):
        mapping = map_twitch_game(
            "game-1",
            "A-B: C™®",
            [SteamGame(11, "A B C")],
        )

        self.assertEqual(mapping.steam_app_id, 11)
        self.assertEqual(mapping.match_method, "exact")

    def test_alias_match_is_manual_and_verified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "aliases.json"
            path.write_text(json.dumps({
                "aliases": {
                    "CS2": {"steam_app_id": 730, "steam_name": "Counter-Strike 2"},
                },
                "mappings": [],
            }), encoding="utf-8")

            mapping = map_twitch_game(
                "730",
                "CS2",
                [],
                manual_aliases_path=path,
            )

        self.assertEqual(mapping.steam_app_id, 730)
        self.assertEqual(mapping.match_method, "alias")
        self.assertTrue(mapping.manual_verified)
        self.assertTrue(mapping.is_reliable)

    def test_explicit_manual_mapping_wins_before_exact_matching(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "aliases.json"
            path.write_text(json.dumps({
                "aliases": {},
                "mappings": [{
                    "twitch_game_id": "tw-1",
                    "twitch_name": "Series Name",
                    "steam_app_id": 22,
                    "steam_name": "Series Name Definitive Edition",
                }],
            }), encoding="utf-8")

            mapping = map_twitch_game(
                "tw-1",
                "Series Name",
                [SteamGame(11, "Series Name")],
                manual_aliases_path=path,
            )

        self.assertEqual(mapping.steam_app_id, 22)
        self.assertEqual(mapping.match_method, "manual")
        self.assertTrue(mapping.manual_verified)

    def test_exact_edition_or_remaster_prefers_the_matching_edition(self):
        mapping = map_twitch_game(
            "tw-remaster",
            "Example Remastered",
            [SteamGame(1, "Example"), SteamGame(2, "Example Remastered")],
        )

        self.assertEqual(mapping.steam_app_id, 2)
        self.assertEqual(mapping.match_method, "exact")

    def test_demos_and_playtests_do_not_map_to_full_games_automatically(self):
        for name in ("Example Demo", "Example Playtest", "Example: Demo"):
            with self.subTest(name=name):
                mapping = map_twitch_game(name, name, [SteamGame(1, "Example")])
                self.assertIsNone(mapping.steam_app_id)
                self.assertFalse(mapping.is_reliable)

    def test_manual_mapping_can_override_demo_exclusion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "aliases.json"
            path.write_text(json.dumps({
                "aliases": {},
                "mappings": [{
                    "twitch_game_id": "demo-1",
                    "twitch_name": "Example Demo",
                    "steam_app_id": 1,
                    "steam_name": "Example",
                }],
            }), encoding="utf-8")

            mapping = map_twitch_game(
                "demo-1",
                "Example Demo",
                [SteamGame(1, "Example")],
                manual_aliases_path=path,
            )

        self.assertEqual(mapping.steam_app_id, 1)
        self.assertTrue(mapping.manual_verified)
        self.assertTrue(mapping.is_reliable)

    def test_duplicate_steam_names_are_left_unresolved(self):
        mapping = map_twitch_game(
            "tw-duplicate",
            "Same Game",
            [SteamGame(1, "Same Game"), SteamGame(2, "Same Game")],
        )

        self.assertIsNone(mapping.steam_app_id)
        self.assertEqual(mapping.match_method, "ambiguous")
        self.assertFalse(mapping.is_reliable)

    def test_high_confidence_fuzzy_match_is_accepted(self):
        mapping = map_twitch_game(
            "tw-fuzzy",
            "Apex Legend",
            [SteamGame(1, "Apex Legends")],
        )

        self.assertEqual(mapping.steam_app_id, 1)
        self.assertEqual(mapping.match_method, "fuzzy")
        self.assertGreaterEqual(mapping.match_score, 0.9)
        self.assertTrue(mapping.is_reliable)

    def test_weak_fuzzy_candidate_is_retained_but_unverified(self):
        mapping = map_twitch_game(
            "tw-weak",
            "Project Aurora Preview",
            [SteamGame(1, "Project Aurora")],
        )

        self.assertEqual(mapping.steam_app_id, 1)
        self.assertEqual(mapping.match_method, "fuzzy")
        self.assertLess(mapping.match_score, 0.9)
        self.assertFalse(mapping.manual_verified)
        self.assertFalse(mapping.is_reliable)

    def test_manual_mapping_is_not_overwritten_by_automatic_mapping(self):
        manual = GameMapping(
            "tw-1", "Same Name", 22, "Curated Name", "manual", 1.0, True
        )
        automatic = GameMapping(
            "tw-1", "Same Name", 11, "Same Name", "exact", 1.0, False
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "mapping.sqlite3"
            connection = sqlite3.connect(database)
            try:
                connection.executescript(SCHEMA)
                ensure_twitch_game_mapping_schema(connection)
                self.assertEqual(persist_game_mappings(connection, [manual], "2026-08-02T00:00:00Z"), 1)
                self.assertEqual(persist_game_mappings(connection, [automatic], "2026-08-03T00:00:00Z"), 0)
                self.assertEqual(persist_game_mappings(connection, [manual], "2026-08-04T00:00:00Z"), 1)
                row = connection.execute(
                    "SELECT steam_app_id, steam_name, match_method, manual_verified, updated_at "
                    "FROM twitch_game_mappings WHERE twitch_game_id = ?",
                    ("tw-1",),
                ).fetchone()
                count = connection.execute("SELECT COUNT(*) FROM twitch_game_mappings").fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(row, (22, "Curated Name", "manual", 1, "2026-08-04T00:00:00Z"))
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()

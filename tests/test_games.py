import unittest

from gamepulse_data.games import build_game_bridges, normalise_game_row


class GameTests(unittest.TestCase):
    def test_normalise_game_row_parses_owner_range_and_review_score(self):
        game = normalise_game_row(
            {
                "AppID": "10", "Name": "Example", "Estimated owners": "20,000 - 50,000",
                "Positive": "90", "Negative": "10", "Price": "12.5", "Genres": "Action,RPG,Action",
            },
            {},
        )
        self.assertEqual(game["steam_app_id"], 10)
        self.assertEqual(game["owners_low"], 20000)
        self.assertEqual(game["owners_high"], 50000)
        self.assertEqual(game["review_score"], 0.9)
        self.assertEqual(build_game_bridges(game)["game_genres"], [
            {"steam_app_id": 10, "value": "Action"},
            {"steam_app_id": 10, "value": "RPG"},
        ])

    def test_normalise_game_row_converts_zero_text_placeholder_to_null(self):
        game = normalise_game_row({"AppID": "10", "Name": "Example", "About the game": "0"}, {})
        self.assertIsNone(game["short_description"])

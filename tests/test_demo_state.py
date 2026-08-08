import unittest

from gamepulse.ui.shared import DemoState, select_game


class DemoStateTests(unittest.TestCase):
    def test_select_game_updates_shared_selection_without_dropping_profile(self):
        state = DemoState(selected_app_id=10, steam_profile="https://steamcommunity.com/id/example")

        updated = select_game(state, 20)

        self.assertEqual(updated.selected_app_id, 20)
        self.assertEqual(updated.steam_profile, state.steam_profile)

    def test_default_state_has_no_profile(self):
        self.assertIsNone(DemoState(selected_app_id=10).steam_profile)


if __name__ == "__main__":
    unittest.main()

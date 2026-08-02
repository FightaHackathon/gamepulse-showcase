"""Home page for selecting the game that flows through the three modes."""

from __future__ import annotations

from gamepulse.catalog import Catalog
from gamepulse.ui.shared import DemoState, render_game_header, select_game


def render(st, catalog: Catalog, state: DemoState) -> DemoState:
    st.title("GamePulse prototype")
    st.caption("Start with one game, then follow the same evidence through player, streamer, and developer perspectives.")
    query = st.text_input("Search the Steam catalogue", key="home_game_search")
    if query.strip():
        results = catalog.search_games(query)
        if results:
            labels = {f"{game.name} · AppID {game.steam_app_id}": game for game in results}
            selected_label = st.selectbox("Choose a game", list(labels))
            state = select_game(state, labels[selected_label].steam_app_id)
        else:
            st.info("No games match that search yet. Try a shorter title, a distinctive word, or clear the search to keep the prepared demo game.")
    game = catalog.get_game(state.selected_app_id)
    render_game_header(st, game)
    st.info("Next action: choose Player, Streamer, or Developer in the sidebar to continue with this selected game.")
    return state

"""GamePulse prototype entry point. Run with: streamlit run app.py"""

from __future__ import annotations

from pathlib import Path

from gamepulse.catalog import Catalog
from gamepulse.config import Settings
from gamepulse.ui.home import render as render_home
from gamepulse.ui.player import render as render_player
from gamepulse.ui.streamer import render as render_streamer
from gamepulse.ui.developer import render as render_developer
from gamepulse.ui.shared import DemoState


def run() -> None:
    try:
        import streamlit as st
    except ModuleNotFoundError as exc:
        raise SystemExit("Streamlit is not installed. Run: python -m pip install -r requirements.txt") from exc

    root = Path(__file__).resolve().parent
    settings = Settings.from_env(root)
    if not settings.database_path.exists():
        st.error("GamePulse cannot start because its prepared demo data is missing.")
        st.info("Why this happened: the local prototype database has not been created or is not in the expected location. Next action: run scripts/build_prototype_database.py, then refresh this page.")
        st.stop()
    catalog = Catalog(settings.database_path)
    candidates = catalog.rank_demo_candidates(1)
    if not candidates:
        st.error("GamePulse cannot start because the prepared demo data has no game ready to show.")
        st.info("Why this happened: the local catalogue is empty or lacks a curated demo candidate. Next action: rebuild the prototype database, then refresh this page.")
        st.stop()
    selected_app_id = settings.demo_selected_app_id or candidates[0].steam_app_id
    try:
        catalog.get_game(selected_app_id)
    except KeyError:
        selected_app_id = candidates[0].steam_app_id
    if "gamepulse_state" not in st.session_state:
        st.session_state.gamepulse_state = DemoState(selected_app_id)
    state = st.session_state.gamepulse_state
    page = st.sidebar.radio("Mode", ["Home", "Player", "Streamer", "Developer"])
    if page == "Home":
        state = render_home(st, catalog, state)
    elif page == "Player":
        state = render_player(st, settings, catalog, state)
    elif page == "Streamer":
        state = render_streamer(st, settings, catalog, state)
    elif page == "Developer":
        state = render_developer(st, settings, catalog, state)
    else:
        st.title(page)
        st.info("This mode is scaffolded next; the selected game remains shared across the prototype.")
        state = render_home(st, catalog, state)
    st.session_state.gamepulse_state = state


if __name__ == "__main__":
    run()

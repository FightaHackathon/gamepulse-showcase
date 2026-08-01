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
        st.error("Prototype database is missing. Build it with scripts/build_prototype_database.py first.")
        st.stop()
    catalog = Catalog(settings.database_path)
    candidates = catalog.rank_demo_candidates(1)
    if not candidates:
        st.error("No suitable curated game exists in the prototype database.")
        st.stop()
    if "gamepulse_state" not in st.session_state:
        st.session_state.gamepulse_state = DemoState(candidates[0].steam_app_id)
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

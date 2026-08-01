"""Player Mode: polished, explainable recommendations with optional Steam context."""

from __future__ import annotations

from dataclasses import replace

from gamepulse.catalog import Catalog
from gamepulse.config import Settings
from gamepulse.player_session import analyze_public_profile, empty_profile_session
from gamepulse.providers.steam import SteamProvider
from gamepulse.recommendations import PlayerPreferences, RecommendationEngine
from gamepulse.ui.player_components import (
    render_personalization,
    render_player_filters,
    render_player_hero,
    render_recommendation_card,
    render_recommendation_empty_state,
)
from gamepulse.ui.player_theme import inject_player_theme
from gamepulse.ui.shared import DemoState


def render(st, settings: Settings, catalog: Catalog, state: DemoState) -> DemoState:
    inject_player_theme(st)
    st.title("Player Mode")
    st.caption("Find your next game from a clear match score, useful evidence, and your own preferences.")

    game = catalog.get_game(state.selected_app_id)
    render_player_hero(st, game)

    if "player_profile_session" not in st.session_state:
        st.session_state.player_profile_session = empty_profile_session()
    profile_state = st.session_state.player_profile_session
    options = catalog.preference_options()
    action = render_personalization(st, profile_state, settings, options)

    if action.kind in {"analyze", "refresh"}:
        provider = SteamProvider(settings.steam_web_api_key)
        profile_state = analyze_public_profile(action.profile_input, provider, catalog)
        st.session_state.player_profile_session = profile_state
        if profile_state.status == "connected":
            st.success(f"Connected · {len(profile_state.owned_app_ids):,} public library games analyzed for this session.")
        elif profile_state.message:
            st.warning(profile_state.message)
    elif action.kind == "clear":
        profile_state = empty_profile_session()
        st.session_state.player_profile_session = profile_state

    inferred = profile_state.preferences if profile_state.status == "connected" else PlayerPreferences()
    preferences = render_player_filters(
        st,
        options,
        initial=PlayerPreferences(
            preferred_tags=inferred.preferred_tags,
            preferred_genres=inferred.preferred_genres,
        ),
    )
    recommendations = RecommendationEngine(settings.database_path).recommend_similar(
        state.selected_app_id,
        preferences,
        excluded_app_ids=set(profile_state.owned_app_ids),
        limit=8,
    )

    st.subheader("Recommended games")
    if recommendations:
        st.caption(f"{len(recommendations)} games ranked for this session · scores are normalized to 100")
        columns = st.columns(2, gap="medium")
        for index, recommendation in enumerate(recommendations):
            with columns[index % 2]:
                render_recommendation_card(st, recommendation, featured=index == 0)
    else:
        render_recommendation_empty_state(st, preferences)

    profile_input = profile_state.profile_input or state.steam_profile
    return replace(state, steam_profile=profile_input or None)

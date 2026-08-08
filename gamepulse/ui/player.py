"""Player Mode: polished, explainable recommendations with optional Steam context."""

from __future__ import annotations

import math
from dataclasses import replace

from gamepulse.catalog import Catalog
from gamepulse.config import Settings
from gamepulse.game_details import get_game_details
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
from gamepulse.ui.game_details_components import render_game_details
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
            source_name = profile_state.library.source_name if profile_state.library else "Steam Web API"
            scope = "public library games" if source_name == "Steam Web API" or (profile_state.library and profile_state.library.complete) else "recent public games"
            st.success(f"Connected · {len(profile_state.owned_app_ids):,} {scope} analyzed for this session.")
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
        limit=400,
    )

    st.subheader("Recommended games")
    if recommendations:
        page_size = 24
        page_count = max(1, math.ceil(len(recommendations) / page_size))
        page_key = "gp_player_recommendation_page"
        current_page = int(st.session_state.get(page_key, 1))
        if current_page < 1 or current_page > page_count:
            current_page = 1
            st.session_state[page_key] = current_page
        page = st.number_input(
            "Recommendation page",
            min_value=1,
            max_value=page_count,
            value=current_page,
            step=1,
            key=page_key,
        )
        st.caption(f"Page {int(page)} of {page_count}")
        start = (page - 1) * page_size
        visible_recommendations = recommendations[start : start + page_size]
        end = start + len(visible_recommendations)
        st.caption(f"{len(recommendations)} games ranked for this session · showing {start + 1}–{end} · scores are normalized to 100")
        columns = st.columns(2, gap="medium")
        for index, recommendation in enumerate(visible_recommendations):
            with columns[index % 2]:
                render_recommendation_card(st, recommendation, featured=index == 0)
                if st.button("View details", key=f"gp_player_view_details_{recommendation.app_id}", use_container_width=True):
                    st.session_state["gp_player_detail_app_id"] = recommendation.app_id
    else:
        render_recommendation_empty_state(st, preferences)

    detail_app_id = st.session_state.get("gp_player_detail_app_id")
    if detail_app_id is not None:
        try:
            details = get_game_details(settings.database_path, int(detail_app_id), review_limit=20)
        except KeyError:
            st.warning("That game is no longer available in the prepared catalogue.")
            st.session_state.pop("gp_player_detail_app_id", None)
        else:
            render_game_details(st, details)
            if st.button("Close details", key="gp_player_close_details", use_container_width=True):
                st.session_state.pop("gp_player_detail_app_id", None)

    profile_input = profile_state.profile_input or state.steam_profile
    return replace(state, steam_profile=profile_input or None)

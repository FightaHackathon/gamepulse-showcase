"""Streamer Mode using the demo/cached/live Twitch provider boundary."""

from __future__ import annotations

from gamepulse.catalog import Catalog
from gamepulse.config import Settings
from gamepulse.providers.twitch import TwitchProvider
from gamepulse.streamer_opportunity import StreamerProfile, evaluate_snapshot_freshness, find_matching_opportunity, score_game_opportunities
from gamepulse.ui.shared import DemoState
from gamepulse.ui.streamer_components import (
    render_opportunity_card,
    render_opportunity_empty_state,
    render_snapshot_status,
    render_streamer_hero,
    render_trending_streamers,
)
from gamepulse.ui.streamer_theme import inject_streamer_theme


def render(st, settings: Settings, catalog: Catalog, state: DemoState) -> DemoState:
    game = catalog.get_game(state.selected_app_id)
    inject_streamer_theme(st)
    st.title("Streamer Mode")
    st.caption("Find audience demand that is still reachable for your channel.")
    render_streamer_hero(st, game)

    provider = TwitchProvider(settings.twitch_snapshot_path, settings.twitch_client_id, settings.twitch_client_secret)
    try:
        snapshot = provider.get_game_trends()
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        st.error(f"Twitch data is temporarily unavailable: {exc}")
        render_opportunity_empty_state(st)
        return state

    freshness = evaluate_snapshot_freshness(snapshot)
    render_snapshot_status(st, snapshot, freshness)

    st.subheader("Channel strategy")
    control_columns = st.columns(2)
    with control_columns[0]:
        tier = st.selectbox(
            "Your channel size",
            ["emerging", "mid-size", "large"],
            format_func=lambda value: value.replace("-", " ").title(),
        )
    with control_columns[1]:
        strategy_label = st.selectbox(
            "What are you optimizing for?",
            ["Balanced", "Reach", "Growth"],
            help="Reach emphasizes viewers per channel. Growth emphasizes the latest positive trend signal.",
        )
    available_tags = sorted({str(tag) for trend in snapshot.data for tag in getattr(trend, "tags", ())}, key=str.casefold)
    selected_tags = st.multiselect("Preferred category tags", available_tags, placeholder="Optional tag preference")
    profile = StreamerProfile(
        preferred_tags=tuple(str(item) for item in selected_tags),
        channel_size_tier=tier,
        strategy=strategy_label.casefold(),
    )
    opportunities = score_game_opportunities(snapshot.data, profile)

    selected = find_matching_opportunity(opportunities, game.name)
    st.subheader("Selected game opportunity")
    if selected:
        render_opportunity_card(st, selected, featured=True)
    else:
        st.info("The selected game is not present in the current Twitch category snapshot.")
        st.caption("Use the ranked opportunities below to compare nearby category signals.")

    st.subheader("Top opportunities")
    if not opportunities:
        render_opportunity_empty_state(st)
    else:
        columns = st.columns(2)
        for index, opportunity in enumerate(opportunities[:6]):
            with columns[index % 2]:
                render_opportunity_card(st, opportunity)

    creator_target = selected or (opportunities[0] if opportunities else None)
    st.subheader("Trending creators")
    if creator_target:
        try:
            creator_snapshot = provider.get_streamers(str(creator_target.game_id))
            render_trending_streamers(st, creator_snapshot)
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            st.info(f"Creator data is temporarily unavailable: {exc}")
    else:
        st.info("Select a category with current Twitch data to see creators.")
    return state

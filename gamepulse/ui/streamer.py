"""Streamer Mode: category opportunities, evidence, and creator context."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from statistics import mean, pstdev
from types import SimpleNamespace
from typing import Any, Mapping

import streamlit as st

from gamepulse.catalog import Catalog
from gamepulse.config import Settings
from gamepulse.database import connect_read_only
from gamepulse.game_mapping import GameMapping
from gamepulse.providers.twitch import Snapshot, TwitchProvider
from gamepulse.streamer_opportunity import (
    HistoricalGameFeatures,
    StreamerProfile,
    evaluate_snapshot_freshness,
    find_matching_opportunity,
    score_game_opportunities,
)
from gamepulse.ui.shared import DemoState
from gamepulse.ui.streamer_components import (
    render_category_deep_dive,
    render_creator_landscape,
    render_opportunity_card,
    render_opportunity_empty_state,
    render_snapshot_status,
    render_streamer_hero,
)
from gamepulse.ui.streamer_theme import inject_streamer_theme


@st.cache_data(ttl=60, show_spinner=False)
def _cached_game_snapshot(
    snapshot_path: str,
    client_id: str | None,
    client_secret: str | None,
    max_pages: int,
    request_timeout_seconds: float,
) -> Snapshot:
    provider = TwitchProvider(
        Path(snapshot_path),
        client_id,
        client_secret,
        max_stream_pages=max_pages,
        request_timeout_seconds=request_timeout_seconds,
    )
    return provider.get_game_trends()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_streamer_snapshot(
    snapshot_path: str,
    client_id: str | None,
    client_secret: str | None,
    max_pages: int,
    request_timeout_seconds: float,
    game_id: str,
) -> Snapshot:
    provider = TwitchProvider(
        Path(snapshot_path),
        client_id,
        client_secret,
        max_stream_pages=max_pages,
        request_timeout_seconds=request_timeout_seconds,
    )
    return provider.get_streamers(game_id)


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return bool(
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
    )


@st.cache_data(ttl=300, show_spinner=False)
def _cached_steam_context(database_path: str) -> tuple[dict[str, GameMapping], dict[int, object], dict[int, dict[str, object]]]:
    """Read mappings and Steam metadata without creating or migrating tables."""

    path = Path(database_path)
    if not path.exists():
        return {}, {}, {}
    try:
        connection = connect_read_only(path)
    except (OSError, sqlite3.Error):
        return {}, {}, {}
    try:
        if not _table_exists(connection, "twitch_game_mappings"):
            return {}, {}, {}
        mappings: dict[str, GameMapping] = {}
        for row in connection.execute(
            """SELECT twitch_game_id, twitch_name, steam_app_id, steam_name,
                      match_method, match_score, manual_verified
               FROM twitch_game_mappings"""
        ):
            mappings[str(row[0])] = GameMapping(
                twitch_game_id=str(row[0]),
                twitch_name=str(row[1]),
                steam_app_id=int(row[2]) if row[2] is not None else None,
                steam_name=str(row[3]) if row[3] is not None else None,
                match_method=str(row[4]),
                match_score=float(row[5] or 0),
                manual_verified=bool(row[6]),
            )

        features: dict[int, object] = {}
        metadata: dict[int, dict[str, object]] = {}
        if not _table_exists(connection, "games"):
            return mappings, features, metadata
        has_genres = _table_exists(connection, "game_genres")
        has_tags = _table_exists(connection, "game_tags")
        for mapping in mappings.values():
            if not mapping.is_reliable or mapping.steam_app_id is None:
                continue
            game_row = connection.execute(
                "SELECT name, review_score FROM games WHERE steam_app_id = ?",
                (mapping.steam_app_id,),
            ).fetchone()
            if game_row is None:
                continue
            genres = tuple(
                str(row[0])
                for row in connection.execute(
                    "SELECT value FROM game_genres WHERE steam_app_id = ? ORDER BY value",
                    (mapping.steam_app_id,),
                )
            ) if has_genres else ()
            tags = tuple(
                str(row[0])
                for row in connection.execute(
                    "SELECT value FROM game_tags WHERE steam_app_id = ? ORDER BY value",
                    (mapping.steam_app_id,),
                )
            ) if has_tags else ()
            features[mapping.steam_app_id] = SimpleNamespace(genres=genres, tags=tags)
            metadata[mapping.steam_app_id] = {
                "name": str(game_row[0]),
                "genres": genres,
                "tags": tags,
                "review_score": game_row[1],
            }
        return mappings, features, metadata
    except sqlite3.Error:
        return {}, {}, {}
    finally:
        connection.close()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_twitch_history(database_path: str, game_id: str) -> tuple[dict[str, object], ...]:
    """Load persisted category history, if the disposable snapshot table exists."""

    path = Path(database_path)
    if not path.exists():
        return ()
    try:
        connection = connect_read_only(path)
    except (OSError, sqlite3.Error):
        return ()
    try:
        if not _table_exists(connection, "twitch_game_snapshots"):
            return ()
        rows = connection.execute(
            """SELECT observed_at, viewer_count, channel_count, viewer_to_channel,
                      top_one_viewer_share, top_five_viewer_share, growth_score,
                      source_mode, source_name, partial_coverage
               FROM twitch_game_snapshots
               WHERE game_id = ?
               ORDER BY observed_at""",
            (str(game_id),),
        )
        return tuple(dict(row) for row in rows)
    except sqlite3.Error:
        return ()
    finally:
        connection.close()


def _historical_features(rows: tuple[dict[str, object], ...]) -> HistoricalGameFeatures | None:
    if not rows:
        return None
    viewers = tuple(int(row["viewer_count"]) for row in rows if row.get("viewer_count") is not None)
    latest = rows[-1]
    growth = latest.get("growth_score")
    numeric_viewers = [float(value) for value in viewers if value >= 0]
    volatility = None
    if len(numeric_viewers) >= 2 and mean(numeric_viewers) > 0:
        volatility = min(1.0, pstdev(numeric_viewers) / mean(numeric_viewers))
    return HistoricalGameFeatures(
        growth_score=float(growth) if growth is not None else None,
        volatility=volatility,
        observation_count=len(rows),
        observation_consistency=min(1.0, len(rows) / 10.0),
        viewer_history=viewers,
        observed_at=str(latest.get("observed_at") or "") or None,
    )


def _historical_context(database_path: Path, trends: list[Any]) -> dict[str, HistoricalGameFeatures]:
    context: dict[str, HistoricalGameFeatures] = {}
    for trend in trends:
        rows = _cached_twitch_history(str(database_path), str(getattr(trend, "game_id", "")))
        features = _historical_features(rows)
        if features is not None:
            context[str(getattr(trend, "game_id", ""))] = features
    return context


def _available_languages(trends: list[Any]) -> list[str]:
    values: set[str] = set()
    for trend in trends:
        distribution = getattr(trend, "language_distribution", ()) or ()
        if isinstance(distribution, Mapping):
            values.update(str(key) for key in distribution)
        else:
            values.update(str(item[0]) for item in distribution if isinstance(item, (tuple, list)) and len(item) == 2)
    return sorted(values, key=str.casefold) or ["en"]


def _competition_pressure(opportunity: Any) -> float:
    components = getattr(opportunity, "components", None)
    competition = getattr(components, "competition", None)
    if competition is None:
        return 1.0
    return max(0.0, min(1.0, 1.0 - float(competition)))


def _category_options(trends: list[Any]) -> list[str]:
    return [str(getattr(trend, "game_id", "")) for trend in trends]


def _remember_category(st, options: list[str], preferred: str | None) -> str | None:
    if not options:
        return None
    current = st.session_state.get("gp_streamer_selected_category_id")
    candidate = current if current in options else preferred if preferred in options else options[0]
    st.session_state["gp_streamer_selected_category_id"] = candidate
    return candidate


def _trend_for_id(trends: list[Any], game_id: str | None) -> Any | None:
    for trend in trends:
        if str(getattr(trend, "game_id", "")) == str(game_id):
            return trend
    return None


def render(st, settings: Settings, catalog: Catalog, state: DemoState) -> DemoState:
    game = catalog.get_game(state.selected_app_id)
    inject_streamer_theme(st)
    st.title("Streamer Mode")
    st.caption("Find audience demand that is still reachable for your channel.")
    render_streamer_hero(st, game)

    try:
        with st.spinner("Loading Twitch category observations…"):
            snapshot = _cached_game_snapshot(
                str(settings.twitch_snapshot_path),
                settings.twitch_client_id,
                settings.twitch_client_secret,
                settings.twitch_max_stream_pages,
                settings.twitch_request_timeout_seconds,
            )
    except (OSError, RuntimeError, ValueError, KeyError, sqlite3.Error) as exc:
        st.error(f"Twitch data is temporarily unavailable: {exc}")
        render_opportunity_empty_state(st)
        return state

    freshness = evaluate_snapshot_freshness(snapshot)
    render_snapshot_status(st, snapshot, freshness)
    trends = list(snapshot.data or [])
    trend_by_id = {str(getattr(trend, "game_id", "")): trend for trend in trends}
    mappings, steam_features, steam_metadata = _cached_steam_context(str(settings.database_path))
    historical_features = _historical_context(settings.database_path, trends)

    tabs = st.tabs(["Game Opportunities", "Category Deep Dive", "Creator Landscape"])
    with tabs[0]:
        st.subheader("Game Opportunities")
        st.caption("Opportunity ranks categories for your channel. Confidence describes the evidence quality separately.")
        control_columns = st.columns(2)
        with control_columns[0]:
            tier = st.selectbox(
                "Your channel size",
                ["emerging", "mid-size", "large"],
                format_func=lambda value: value.replace("-", " ").title(),
                key="gp_streamer_channel_tier",
            )
        with control_columns[1]:
            strategy_label = st.selectbox(
                "What are you optimizing for?",
                ["Balanced", "Reach", "Growth", "Community"],
                help="Each strategy changes the explicit opportunity component weights.",
                key="gp_streamer_strategy",
            )

        languages = _available_languages(trends)
        genre_options = sorted({str(item) for item in getattr(game, "genres", ())}, key=str.casefold)
        steam_tag_options = sorted({str(item) for item in getattr(game, "tags", ())}, key=str.casefold)
        twitch_tag_options = sorted({str(tag) for trend in trends for tag in getattr(trend, "tags", ())}, key=str.casefold)
        selected_languages = st.multiselect("Preferred languages", languages, key="gp_streamer_languages")
        selected_genres = st.multiselect("Preferred Steam genres", genre_options, key="gp_streamer_genres")
        selected_steam_tags = st.multiselect("Preferred Steam tags", steam_tag_options, key="gp_streamer_steam_tags")
        selected_twitch_tags = st.multiselect("Preferred Twitch tags", twitch_tag_options, key="gp_streamer_twitch_tags")

        viewer_max = max((int(getattr(trend, "viewer_count", 0) or 0) for trend in trends), default=0)
        min_viewers = st.slider(
            "Minimum observed viewers",
            min_value=0,
            max_value=max(1, viewer_max),
            value=0,
            step=max(1, max(1, viewer_max) // 100),
            key="gp_streamer_min_viewers",
        )
        max_competition = st.slider(
            "Maximum competition",
            min_value=0.0,
            max_value=1.0,
            value=1.0,
            step=0.05,
            help="Competition pressure is a directional crowding signal; lower values are more selective.",
            key="gp_streamer_max_competition",
        )
        include_twitch_only = st.checkbox(
            "Include Twitch-only categories",
            value=True,
            help="Keep categories without a sufficiently reliable Steam mapping in the ranking.",
            key="gp_streamer_include_twitch_only",
        )

        profile = StreamerProfile(
            preferred_tags=tuple(str(item) for item in selected_twitch_tags),
            channel_size_tier=tier,
            strategy=strategy_label.casefold(),
            preferred_genres=tuple(str(item) for item in selected_genres),
            preferred_steam_tags=tuple(str(item) for item in selected_steam_tags),
            preferred_twitch_tags=tuple(str(item) for item in selected_twitch_tags),
            preferred_languages=tuple(str(item) for item in selected_languages),
        )
        opportunities = score_game_opportunities(
            snapshot,
            profile,
            historical_features=historical_features,
            verified_steam_mappings=mappings,
            steam_features=steam_features,
        )
        filtered_opportunities = [
            opportunity
            for opportunity in opportunities
            if opportunity.viewer_count >= min_viewers
            and _competition_pressure(opportunity) <= max_competition
            and (include_twitch_only or opportunity.steam_app_id is not None)
        ]

        selected = find_matching_opportunity(filtered_opportunities, game.name)
        st.subheader("Selected game opportunity")
        if selected:
            render_opportunity_card(st, selected, featured=True)
        elif trends:
            st.info("The selected game is not present in the current filtered category ranking.")
            st.caption("Use the ranked categories below or relax the filters to include it.")
        else:
            render_opportunity_empty_state(st)

        st.subheader("Ranked categories")
        if not filtered_opportunities:
            render_opportunity_empty_state(st, "No categories match the current filters.")
        else:
            columns = st.columns(2)
            for index, opportunity in enumerate(filtered_opportunities[:8]):
                with columns[index % 2]:
                    render_opportunity_card(st, opportunity)

        preferred_category_id = str(selected.game_id) if selected else (str(filtered_opportunities[0].game_id) if filtered_opportunities else None)
        category_options = _category_options(filtered_opportunities or trends)
        _remember_category(st, category_options, preferred_category_id)

    selected_category_id = st.session_state.get("gp_streamer_selected_category_id")
    selected_trend = _trend_for_id(trends, selected_category_id)
    if selected_trend is None and trends:
        selected_category_id = str(getattr(trends[0], "game_id", ""))
        st.session_state["gp_streamer_selected_category_id"] = selected_category_id
        selected_trend = trends[0]

    with tabs[1]:
        st.subheader("Category Deep Dive")
        deep_dive_options = _category_options(trends)
        if not deep_dive_options:
            render_opportunity_empty_state(st, "No Twitch category observations are available for a deep dive.")
        else:
            selected_category_id = st.selectbox(
                "Category to inspect",
                deep_dive_options,
                index=deep_dive_options.index(selected_category_id) if selected_category_id in deep_dive_options else 0,
                format_func=lambda value: str(getattr(trend_by_id.get(value), "name", value)),
                key="gp_streamer_deep_dive_category",
            )
            st.session_state["gp_streamer_selected_category_id"] = selected_category_id
            selected_trend = trend_by_id[selected_category_id]
            history = _cached_twitch_history(str(settings.database_path), selected_category_id)
            mapping = mappings.get(selected_category_id)
            mapped_metadata = steam_metadata.get(mapping.steam_app_id) if mapping and mapping.is_reliable and mapping.steam_app_id else None
            render_category_deep_dive(
                st,
                selected_trend,
                history=history,
                freshness_label=f"{snapshot.mode} · {freshness.label}",
                steam_metadata=mapped_metadata,
            )

    with tabs[2]:
        st.subheader("Creator Landscape")
        st.caption("Informational category context — this is not the developer promotion ranking.")
        if selected_category_id is None:
            st.info("Select a category with current Twitch observations to see its creators.")
        else:
            try:
                with st.spinner("Loading creators observed in this category…"):
                    creator_snapshot = _cached_streamer_snapshot(
                        str(settings.twitch_snapshot_path),
                        settings.twitch_client_id,
                        settings.twitch_client_secret,
                        settings.twitch_max_stream_pages,
                        settings.twitch_request_timeout_seconds,
                        str(selected_category_id),
                    )
                render_creator_landscape(st, creator_snapshot)
            except (OSError, RuntimeError, ValueError, KeyError, sqlite3.Error) as exc:
                st.info(f"Creator data is temporarily unavailable: {exc}")
    return state

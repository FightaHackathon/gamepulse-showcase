"""Developer Mode: a decision-ready market and creator-signal dashboard."""

from __future__ import annotations

from gamepulse.catalog import Catalog
from gamepulse.config import Settings
from gamepulse.forecasting import daily_counts_for_game, forecast_review_activity
from gamepulse.market_analysis import (
    MarketSnapshot,
    analyze_developer_opportunity,
    analyze_market,
    latest_market_snapshot,
)
from gamepulse.providers.twitch import TwitchProvider
from gamepulse.review_analysis import analyze_reviews
from gamepulse.streamer_fit import StreamerProfile, rank_streamers
from gamepulse.streamer_opportunity import find_matching_opportunity
from gamepulse.ui.developer_components import (
    render_comparable_card,
    render_creator_fit_card,
    render_developer_hero,
    render_opportunity_summary,
    render_signal_card,
)
from gamepulse.ui.developer_theme import inject_developer_theme
from gamepulse.ui.shared import DemoState


def _owner_label(snapshot: MarketSnapshot) -> str:
    if snapshot.owners_low is None or snapshot.owners_high is None:
        return "Unavailable"
    return f"{snapshot.owners_low:,}–{snapshot.owners_high:,}"


def _gross_label(analysis) -> str:
    if analysis.estimated_gross_low is None or analysis.estimated_gross_high is None:
        return "Unavailable"
    return f"${analysis.estimated_gross_low:,.0f}–${analysis.estimated_gross_high:,.0f}"


def _player_metric_label(snapshot: MarketSnapshot) -> str:
    return "Current players" if snapshot.player_metric == "current" else "Peak CCU"


def _gross_detail(snapshot: MarketSnapshot) -> str:
    if snapshot.discount_pct is None:
        return "Owners × current price scenario; not verified revenue"
    return f"Owners × current price; {snapshot.discount_pct:.0f}% store discount observed; not verified revenue"


def _creator_fits(settings: Settings, game):
    provider = TwitchProvider(settings.twitch_snapshot_path, settings.twitch_client_id, settings.twitch_client_secret)
    try:
        trend_snapshot = provider.get_game_trends()
        target_category = find_matching_opportunity(trend_snapshot.data, game.name)
        stream_snapshot = provider.get_streamers(target_category.game_id) if target_category else None
    except (OSError, RuntimeError, ValueError, KeyError):
        return None, []
    if stream_snapshot is None:
        return None, []
    profiles = [
        StreamerProfile(
            item.streamer_id,
            set(item.tags) | {item.game_name},
            item.language,
            item.channel_size_tier,
            item.viewer_count,
        )
        for item in stream_snapshot.data
    ]
    fits = rank_streamers({"genres": set(game.genres), "tags": set(game.tags), "language": "en"}, profiles)
    return stream_snapshot, fits


def render(st, settings: Settings, catalog: Catalog, state: DemoState) -> DemoState:
    game = catalog.get_game(state.selected_app_id)
    inject_developer_theme(st)
    st.title("Developer Mode")
    st.caption("Turn public market, review, and creator signals into a next-step validation brief.")

    snapshot = latest_market_snapshot(settings.database_path, game.steam_app_id) or MarketSnapshot(
        game.steam_app_id,
        None,
        game.owners_low,
        game.owners_high,
        game.price_usd,
        game.total_reviews,
        game.peak_ccu,
        "Local prepared data",
        "Steam/Kaggle prepared snapshot",
        "2026-08-01",
    )
    render_developer_hero(st, game, snapshot.source_mode)

    comparables = catalog.comparable_games(game.steam_app_id, limit=5)
    comparable_records = [
        {
            "name": item.name,
            "price_usd": item.price_usd,
            "review_score": item.review_score,
            "owners_high": item.owners_high,
        }
        for item in comparables
    ]
    analysis = analyze_market(snapshot, comparable_records)
    review_analysis = analyze_reviews(settings.database_path, game.steam_app_id)
    forecast = forecast_review_activity(daily_counts_for_game(settings.database_path, game.steam_app_id))
    stream_snapshot, fits = _creator_fits(settings, game)
    opportunity = analyze_developer_opportunity(
        snapshot,
        review_analysis,
        forecast,
        len(fits),
        len(comparables),
        creator_scores=tuple(fit.score for fit in fits),
    )

    st.subheader("Opportunity score")
    render_opportunity_summary(st, opportunity)

    st.subheader("Public market signals")
    signal_columns = st.columns(3)
    render_signal_card(signal_columns[0], "Estimated owners", _owner_label(snapshot), "Public estimate; not a verified download count")
    render_signal_card(signal_columns[1], _player_metric_label(snapshot), f"{snapshot.peak_ccu:,}" if snapshot.peak_ccu else "Unavailable", "Observed concurrent players; current or peak depends on source")
    render_signal_card(signal_columns[2], "Gross scenario", _gross_label(analysis), _gross_detail(snapshot))
    st.caption(analysis.disclaimer)
    st.caption(f"Source: {snapshot.source_mode} · {snapshot.source_name} · observed {snapshot.observed_at} · confidence {snapshot.confidence}")

    st.subheader("Comparable games")
    if analysis.comparable_games:
        comparable_columns = st.columns(2)
        for index, comparable in enumerate(comparables):
            render_comparable_card(comparable_columns[index % 2], comparable)
    else:
        st.info("No comparable games were found from shared catalog tags or genres.")

    st.subheader("Review themes")
    st.write(f"{review_analysis.review_count:,} reviews analyzed · {review_analysis.positive_ratio:.1%} recommended")
    st.caption("Positive themes: " + (", ".join(review_analysis.positive_themes) or "Not enough data"))
    st.caption("Negative themes: " + (", ".join(review_analysis.negative_themes) or "Not enough data"))

    st.subheader("30-day interest forecast")
    forecast_columns = st.columns(2)
    render_signal_card(forecast_columns[0], "Expected new reviews", f"{forecast.low:,}–{forecast.high:,}", f"Central estimate {forecast.expected:,} over {forecast.horizon_days} days")
    render_signal_card(forecast_columns[1], "Forecast baseline", forecast.method, "Review activity only; not a sales or download forecast")
    st.caption(f"Method: {forecast.method}; based on collected review activity, not verified sales or downloads.")

    st.subheader("Streamer fit shortlist")
    if stream_snapshot is None:
        st.info("The selected game is not present in the current Twitch category snapshot.")
    else:
        st.caption(f"Source: {stream_snapshot.mode} · {stream_snapshot.source_name} · observed {stream_snapshot.observed_at}")
        if not fits:
            st.info("No creator observations are available for this category.")
        else:
            creator_columns = st.columns(2)
            for index, fit in enumerate(fits[:6]):
                render_creator_fit_card(creator_columns[index % 2], fit)
    return state

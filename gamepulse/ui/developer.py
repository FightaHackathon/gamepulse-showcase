"""Developer Mode: market evidence and directional promotion fit."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from statistics import mean, median, pstdev
from typing import Any, Mapping

import streamlit as st

from gamepulse.catalog import Catalog
from gamepulse.config import Settings
from gamepulse.creator_aggregation import aggregate_creator_categories, deduplicate_observations
from gamepulse.database import connect_read_only
from gamepulse.forecasting import daily_counts_for_game, forecast_review_activity
from gamepulse.growth_windows import calculate_window_growth
from gamepulse.market_analysis import (
    MarketSnapshot,
    analyze_developer_opportunity,
    analyze_market,
    latest_market_snapshot,
)
from gamepulse.providers.twitch import Snapshot, TwitchProvider
from gamepulse.review_analysis import analyze_reviews
from gamepulse.streamer_fit import (
    CREATOR_TIER_ORDER,
    PromotionCampaignProfile,
    StreamerProfile,
    classify_creator_tier,
    normalize_creator_tier,
    rank_streamers,
)
from gamepulse.streamer_opportunity import find_matching_opportunity
from gamepulse.ui.developer_components import (
    creator_fits_csv,
    render_comparable_card,
    render_creator_comparison,
    render_creator_fit_card,
    render_developer_hero,
    render_opportunity_summary,
    render_signal_card,
)
from gamepulse.ui.developer_theme import inject_developer_theme
from gamepulse.ui.shared import DemoState


OBJECTIVES = ("Awareness", "Wishlist growth", "Demo discovery", "Launch promotion", "Community building")
BUDGET_POSITIONS = ("Micro", "Small", "Medium", "Flexible")
STREAMER_TIERS = CREATOR_TIER_ORDER


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


def _provider_args(settings: Settings) -> tuple[str, str | None, str | None, int, float]:
    return (
        str(settings.twitch_snapshot_path),
        settings.twitch_client_id,
        settings.twitch_client_secret,
        settings.twitch_max_stream_pages,
        settings.twitch_request_timeout_seconds,
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_game_trends(
    snapshot_path: str,
    client_id: str | None,
    client_secret: str | None,
    max_pages: int,
    request_timeout_seconds: float,
) -> Snapshot:
    return TwitchProvider(
        Path(snapshot_path),
        client_id,
        client_secret,
        max_stream_pages=max_pages,
        request_timeout_seconds=request_timeout_seconds,
    ).get_game_trends()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_category_streamers(
    snapshot_path: str,
    client_id: str | None,
    client_secret: str | None,
    max_pages: int,
    request_timeout_seconds: float,
    game_id: str,
) -> Snapshot:
    return TwitchProvider(
        Path(snapshot_path),
        client_id,
        client_secret,
        max_stream_pages=max_pages,
        request_timeout_seconds=request_timeout_seconds,
    ).get_streamers(str(game_id))


@st.cache_data(ttl=300, show_spinner=False)
def _cached_streamer_history(database_path: str) -> tuple[dict[str, object], ...]:
    path = Path(database_path)
    if not path.exists():
        return ()
    try:
        connection = connect_read_only(path)
    except (OSError, sqlite3.Error):
        return ()
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'twitch_streamer_snapshots'"
        ).fetchone()
        if not exists:
            return ()
        columns = {row[1] for row in connection.execute("PRAGMA table_info(twitch_streamer_snapshots)")}
        partial_column = "partial_coverage" if "partial_coverage" in columns else "0 AS partial_coverage"
        rows = connection.execute(
            f"""SELECT observed_at, stream_id, streamer_id, streamer_name, streamer_login,
                      game_id, game_name, viewer_count, language, tags_json,
                      channel_size_tier, broadcaster_type, profile_image_url,
                      source_mode, source_name, {partial_column}
               FROM twitch_streamer_snapshots
               ORDER BY observed_at, streamer_id"""
        )
        return tuple(dict(row) for row in rows)
    except sqlite3.Error:
        return ()
    finally:
        connection.close()


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _normalized(value: object) -> str:
    return " ".join("".join(character if character.isalnum() else " " for character in str(value or "").casefold()).split())


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _tags(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    try:
        return tuple(str(item) for item in value if str(item).strip())
    except TypeError:
        return ()


def _observation_record(item: Any) -> dict[str, object]:
    streamer_id = str(_field(item, "streamer_id", "unknown"))
    return {
        "observed_at": _field(item, "observed_at"),
        "stream_id": _field(item, "stream_id") or f"streamer:{streamer_id}",
        "streamer_id": streamer_id,
        "streamer_name": str(_field(item, "name") or _field(item, "streamer_name") or streamer_id),
        "streamer_login": _field(item, "login_name") or _field(item, "streamer_login"),
        "game_id": str(_field(item, "game_id", "")),
        "game_name": str(_field(item, "game_name", "")),
        "viewer_count": int(_field(item, "viewer_count", 0) or 0),
        "language": str(_field(item, "language", "") or ""),
        "tags": _tags(_field(item, "tags", ())),
        "channel_size_tier": str(_field(item, "channel_size_tier", "unknown") or "unknown"),
        "profile_image_url": _field(item, "profile_image_url") or _field(item, "profile_image"),
        "source_mode": _field(item, "source_mode", "Unknown"),
        "source_name": _field(item, "source_name", ""),
        "partial_coverage": bool(_field(item, "partial_coverage", False)),
        "collection_id": _field(item, "collection_id"),
    }


def _history_record(row: Mapping[str, object]) -> dict[str, object]:
    try:
        raw_tags = json.loads(str(row.get("tags_json") or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        raw_tags = ()
    record = dict(row)
    record["tags"] = _tags(raw_tags)
    record["streamer_id"] = str(row.get("streamer_id") or "unknown")
    record["streamer_name"] = str(row.get("streamer_name") or record["streamer_id"])
    record["viewer_count"] = int(row.get("viewer_count") or 0)
    record["game_name"] = str(row.get("game_name") or "")
    record["language"] = str(row.get("language") or "")
    record["source_mode"] = row.get("source_mode") or "Unknown"
    record["source_name"] = str(row.get("source_name") or "")
    record["record_origin"] = "historical"
    record["partial_coverage"] = bool(row.get("partial_coverage"))
    record["collection_id"] = row.get("collection_id")
    return record


def _canonical_source_mode(value: object) -> str:
    raw = str(value or "").strip().casefold()
    if "mixed" in raw:
        return "Mixed"
    if "fallback" in raw:
        return "Fallback"
    if "live" in raw:
        return "Live"
    if "demo" in raw:
        return "Demo"
    if "manual" in raw:
        return "Manual"
    if "cached" in raw or "snapshot" in raw:
        return "Cached/Snapshot"
    return "Unknown"


def _record_origin(record: Mapping[str, object]) -> str | None:
    value = str(record.get("record_origin") or "").strip().casefold()
    if value in {"current", "provider", "live"}:
        return "current"
    if value in {"historical", "history", "persisted"}:
        return "historical"
    return None


def _source_mode_for_record(record: Mapping[str, object]) -> str:
    if _record_origin(record) == "historical":
        return "Historical"
    mode = _canonical_source_mode(record.get("source_mode"))
    if mode in {"Live", "Demo", "Fallback"}:
        return mode
    if mode in {"Cached/Snapshot", "Manual"}:
        return "Historical" if _record_origin(record) != "current" else "Demo"
    return mode


def _collection_identifier(record: Mapping[str, object]) -> str:
    existing = record.get("collection_id")
    if existing:
        return str(existing)
    values = tuple(str(record.get(key) or "") for key in ("source_mode", "source_name", "observed_at"))
    return "|".join(values) if any(values) else ""


def _profile_from_records(
    streamer_id: str,
    records: list[dict[str, object]],
    target_name: str,
    similar_names: tuple[str, ...],
    _legacy_source_mode: str | None = None,
    _legacy_observed_at: str | None = None,
) -> StreamerProfile:
    deduplicated = deduplicate_observations(records)
    ordered = sorted(deduplicated, key=lambda record: _parse_time(record.get("observed_at")) or datetime.min.replace(tzinfo=timezone.utc))
    dated_records = [record for record in ordered if _parse_time(record.get("observed_at")) is not None]
    latest = dated_records[-1] if dated_records else (ordered[-1] if ordered else {})
    observed_at = str(latest.get("observed_at")) if _parse_time(latest.get("observed_at")) is not None else None
    source_modes = tuple(dict.fromkeys(_canonical_source_mode(row.get("source_mode")) for row in ordered))
    if any(_record_origin(row) for row in ordered):
        source_modes = tuple(dict.fromkeys(_source_mode_for_record(row) for row in ordered))
    source_mode = source_modes[0] if len(source_modes) == 1 else "Mixed" if source_modes else "Unknown"
    source_names = tuple(dict.fromkeys(str(row.get("source_name") or "") for row in ordered if str(row.get("source_name") or "").strip()))
    source_name = "Mixed sources" if source_mode == "Mixed" else latest.get("source_name") or (source_names[0] if source_names else "")
    collection_ids = tuple(dict.fromkeys(_collection_identifier(row) for row in ordered if _collection_identifier(row)))
    partial_coverage = any(bool(row.get("partial_coverage")) for row in ordered)
    provenance_parts: list[str] = []
    if source_mode == "Mixed":
        labels = ", ".join(source_names[:2]) or ", ".join(source_modes)
        suffix = " and more" if len(source_names) > 2 else ""
        provenance_parts.append(f"Mixed provenance ({', '.join(source_modes)}) across {labels}{suffix}.")
    elif source_mode == "Historical":
        provenance_parts.append("Historical creator observations come from persisted Twitch snapshots.")
    if len(collection_ids) > 1:
        provenance_parts.append(f"{len(collection_ids)} collections contributed.")
    if partial_coverage:
        provenance_parts.append("Partial coverage exists in contributing data.")
    provenance_note = " ".join(provenance_parts)
    category_aggregation = aggregate_creator_categories(ordered)
    game_names = category_aggregation.display_categories
    tags = tuple(dict.fromkeys(tag for row in ordered for tag in _tags(row.get("tags"))))
    categories = set(game_names) | set(tags)
    similar_set = {_normalized(name) for name in similar_names}
    similar_history = tuple(name for name in game_names if _normalized(name) in similar_set)
    viewers = [max(0, int(row.get("viewer_count") or 0)) for row in ordered]
    average = int(round(mean(viewers))) if viewers else 0
    median_value = float(median(viewers)) if viewers else None
    peak = float(max(viewers)) if viewers else None
    volatility = None
    if len(viewers) >= 2 and mean(viewers) > 0:
        volatility = min(1.0, pstdev(viewers) / mean(viewers))
    primary_category = category_aggregation.primary_category
    primary_share = category_aggregation.primary_category_share
    growth_comparison = calculate_window_growth(deduplicated, "seven-day")
    languages = tuple(dict.fromkeys(str(row.get("language") or "") for row in ordered if str(row.get("language") or "").strip()))
    login = latest.get("streamer_login")
    channel_url = f"https://twitch.tv/{login}" if login else None
    latest_viewers = latest.get("viewer_count")
    current_viewers = average if latest_viewers in (None, "") else latest_viewers
    tier = classify_creator_tier(current_viewers, len(ordered), viewers)
    return StreamerProfile(
        streamer_id=str(streamer_id),
        categories=categories,
        language=languages[0] if languages else "",
        tier=tier,
        average_viewers=average,
        name=str(latest.get("streamer_name") or streamer_id),
        category_history=game_names,
        similar_game_history=similar_history,
        median_viewers=median_value,
        peak_viewers=peak,
        primary_category=primary_category,
        primary_category_share=primary_share,
        viewer_volatility=volatility,
        observation_count=len(ordered),
        seven_day_growth=growth_comparison.percentage_change,
        seven_day_growth_interval_hours=growth_comparison.actual_interval_hours,
        seven_day_growth_baseline_at=growth_comparison.baseline_timestamp,
        seven_day_growth_latest_at=growth_comparison.latest_timestamp,
        languages=languages,
        source_mode=source_mode,
        observed_at=observed_at,
        partial_coverage=partial_coverage,
        source_name=str(source_name or ""),
        provenance_note=provenance_note,
        collection_ids=collection_ids,
        profile_image_url=latest.get("profile_image_url"),
        twitch_channel_url=channel_url,
        login_name=str(login) if login else None,
    )


def _related_names(catalog: Catalog, game, trends: list[Any]) -> tuple[str, ...]:
    comparable_names = tuple(item.name for item in catalog.comparable_games(game.steam_app_id, limit=3))
    normalized = {_normalized(name) for name in comparable_names}
    trend_names = [str(_field(trend, "name", "")) for trend in trends]
    matched = [name for name in trend_names if _normalized(name) in normalized and _normalized(name) != _normalized(game.name)]
    return tuple(dict.fromkeys(matched))


def _creator_data(settings: Settings, catalog: Catalog, game):
    args = _provider_args(settings)
    try:
        trend_snapshot = _cached_game_trends(*args)
        target_category = find_matching_opportunity(trend_snapshot.data, game.name)
        if target_category is None:
            return None, [], (), {}
        similar_names = _related_names(catalog, game, trend_snapshot.data)
        related_ids = [str(target_category.game_id)] + [
            str(trend.game_id) for trend in trend_snapshot.data
            if _normalized(_field(trend, "name", "")) in {_normalized(name) for name in similar_names}
        ]
        snapshots = [_cached_category_streamers(*args, category_id) for category_id in dict.fromkeys(related_ids)]
        target_snapshot = snapshots[0]
        provider_records = []
        for snapshot in snapshots:
            for item in snapshot.data:
                record = _observation_record(item)
                record["observed_at"] = snapshot.observed_at
                record["source_mode"] = snapshot.mode
                record["source_name"] = snapshot.source_name
                record["record_origin"] = "current"
                record["partial_coverage"] = bool(record.get("partial_coverage")) or bool(snapshot.partial_coverage)
                record["collection_id"] = "|".join((snapshot.mode, snapshot.source_name, snapshot.observed_at))
                provider_records.append(record)
        history_rows = _cached_streamer_history(str(settings.database_path))
        allowed_ids = {str(record["streamer_id"]) for record in provider_records}
        relevant_names = {
            _normalized(game.name),
            _normalized(_field(target_category, "name", "")),
            *(_normalized(name) for name in similar_names),
        }
        history_records = [
            _history_record(row)
            for row in history_rows
            if str(row.get("streamer_id")) in allowed_ids
            or _normalized(row.get("game_name", "")) in relevant_names
        ]
        records = list(deduplicate_observations(provider_records + history_records))
        by_streamer: dict[str, list[dict[str, object]]] = {}
        for record in records:
            by_streamer.setdefault(str(record["streamer_id"]), []).append(record)
        profiles = [
            _profile_from_records(streamer_id, creator_records, game.name, similar_names)
            for streamer_id, creator_records in sorted(by_streamer.items())
        ]
        baseline_campaign = PromotionCampaignProfile(
            game_name=game.name,
            steam_app_id=game.steam_app_id,
            genres=tuple(game.genres),
            tags=tuple(game.tags),
            similar_games=similar_names,
            promotion_objective="awareness",
        )
        baseline_profiles = [profile for profile in profiles if _fit_has_selected_history(profile, game.name)]
        baseline_fits = rank_streamers(baseline_campaign, baseline_profiles)
        return target_snapshot, profiles, similar_names, {fit.streamer_id: fit for fit in baseline_fits}
    except (OSError, RuntimeError, ValueError, KeyError, sqlite3.Error):
        return None, [], (), {}


def _language_options(profiles: list[StreamerProfile]) -> list[str]:
    values = sorted({language for profile in profiles for language in profile.languages if language}, key=str.casefold)
    return values or ["en"]


def _fit_language_matches(fit, target_languages: tuple[str, ...]) -> bool:
    if not target_languages:
        return True
    return bool(fit.language and fit.language.casefold() in {language.casefold() for language in target_languages})


def filter_creator_fits_by_tier(fits: list[Any], selected_tiers: tuple[str, ...] | list[str]) -> list[Any]:
    """Keep fits in the selected directional audience-size bands."""

    selected = {
        normalize_creator_tier(value)
        for value in selected_tiers
        if normalize_creator_tier(value) != "unknown"
    }
    if not selected:
        return list(fits)
    return [fit for fit in fits if normalize_creator_tier(getattr(fit, "channel_tier", "")) in selected]


def _fit_has_selected_history(profile: StreamerProfile, game_name: str) -> bool:
    return _normalized(game_name) in {_normalized(value) for value in profile.category_history}


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
    st.subheader("Selected game")
    render_developer_hero(st, game, "Local prepared data")

    comparables = catalog.comparable_games(game.steam_app_id, limit=5)
    comparable_records = [
        {"name": item.name, "price_usd": item.price_usd, "review_score": item.review_score, "owners_high": item.owners_high}
        for item in comparables
    ]
    analysis = analyze_market(snapshot, comparable_records)
    review_analysis = analyze_reviews(settings.database_path, game.steam_app_id)
    forecast = forecast_review_activity(daily_counts_for_game(settings.database_path, game.steam_app_id))
    stream_snapshot, profiles, similar_names, baseline_fits = _creator_data(settings, catalog, game)
    opportunity = analyze_developer_opportunity(
        snapshot,
        review_analysis,
        forecast,
        len(baseline_fits),
        len(comparables),
        creator_scores=tuple(fit.score for fit in baseline_fits.values()),
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
        return state

    st.caption(f"Source: {stream_snapshot.mode} · {stream_snapshot.source_name} · observed {stream_snapshot.observed_at}")
    if not profiles:
        st.info("No creator observations are available for this category.")
        return state

    st.caption("Promotion fit is directional public-signal evidence. Budget positioning is context only; no sponsorship prices are estimated.")
    st.caption("Creator tiers are directional audience-size bands based on viewers, not sponsorship-price bands.")
    controls = st.columns(2)
    with controls[0]:
        objective_label = st.selectbox("Promotion objective", OBJECTIVES, key="developer_promotion_objective")
        languages = _language_options(profiles)
        default_languages = ["en"] if "en" in languages else []
        target_languages = st.multiselect("Target languages", languages, default=default_languages, key="developer_target_languages")
        preferred_tiers = st.multiselect(
            "Preferred streamer tiers",
            list(STREAMER_TIERS),
            key="developer_preferred_tiers",
            help="Directional audience-size bands based on viewers; these are not sponsorship-price bands.",
        )
        budget_position = st.selectbox("Budget positioning", BUDGET_POSITIONS, index=3, key="developer_budget_position")
    with controls[1]:
        recommendation_count = st.slider("Recommendation count", min_value=1, max_value=10, value=6, key="developer_recommendation_count")
        require_selected_history = st.checkbox("Require selected-game history", value=False, key="developer_require_selected_history")
        include_similar = st.checkbox("Include similar-game specialists", value=True, key="developer_include_similar")
        st.caption(f"Objective: {objective_label} · Budget positioning: {budget_position} · No sponsorship prices are generated.")

    campaign = PromotionCampaignProfile(
        game_name=game.name,
        steam_app_id=game.steam_app_id,
        genres=tuple(game.genres),
        tags=tuple(game.tags),
        similar_games=similar_names,
        target_languages=tuple(target_languages),
        preferred_streamer_tiers=tuple(preferred_tiers),
        budget_tier=budget_position.casefold(),
        promotion_objective=objective_label.casefold(),
    )
    st.subheader("Campaign summary")
    summary_columns = st.columns(4)
    language_summary = ", ".join(target_languages) or "Any language"
    tier_summary = ", ".join(preferred_tiers) or "Any tier"
    render_signal_card(summary_columns[0], "Selected game", game.name, "Campaign target")
    render_signal_card(summary_columns[1], "Objective", objective_label, "Promotion goal")
    render_signal_card(summary_columns[2], "Audience filters", f"{language_summary} · {tier_summary}", "Target language and audience tier")
    render_signal_card(summary_columns[3], "Recommendations", str(recommendation_count), "Cards to review")
    st.caption(
        f"Budget positioning: {budget_position} · Similar-game specialists: {'included' if include_similar else 'excluded'} · "
        f"Selected-game history: {'required' if require_selected_history else 'optional'}."
    )
    profiles_by_id = {profile.streamer_id: profile for profile in profiles}
    candidate_profiles = [
        profile for profile in profiles
        if include_similar or _fit_has_selected_history(profile, game.name)
    ]
    fits = rank_streamers(campaign, candidate_profiles)
    if require_selected_history:
        fits = [fit for fit in fits if _fit_has_selected_history(profiles_by_id[fit.streamer_id], game.name)]
    if preferred_tiers:
        fits = filter_creator_fits_by_tier(fits, preferred_tiers)
    if target_languages:
        fits = [fit for fit in fits if _fit_language_matches(fit, tuple(target_languages))]
    recommended = fits[:recommendation_count]

    st.subheader("Recommendation cards")
    if not recommended:
        st.info("No streamers match the selected campaign filters.")
        st.caption("Relax the history, language, or tier filters, or include similar-game specialists.")
        return state

    creator_columns = st.columns(2)
    for index, fit in enumerate(recommended):
        with creator_columns[index % 2]:
            render_creator_fit_card(st, fit)

    compare_options = [fit.streamer_id for fit in recommended]
    selected_compare_ids = st.multiselect(
        "Compare recommended streamers",
        compare_options,
        format_func=lambda value: next((fit.streamer_name for fit in recommended if fit.streamer_id == value), value),
        key="developer_compare_streamers",
        help="Choose two or three profiles for a side-by-side component comparison.",
    )
    compared = [fit for fit in recommended if fit.streamer_id in selected_compare_ids][:3]
    render_creator_comparison(st, compared)

    st.download_button(
        "Download streamer recommendations CSV",
        data=creator_fits_csv(recommended),
        file_name="gamepulse_streamer_recommendations.csv",
        mime="text/csv",
        key="developer_streamer_csv",
    )
    return state

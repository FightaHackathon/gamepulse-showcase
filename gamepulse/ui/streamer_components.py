"""Focused Streamlit rendering primitives for Streamer Mode.

The rendering layer deliberately knows nothing about scoring or persistence.  It
only formats provider output, keeps provenance visible, and escapes values that
originated in Twitch metadata before inserting them into the small amount of
HTML used by the Streamer theme.
"""

from __future__ import annotations

from datetime import datetime, timezone
import html
from statistics import mean
from typing import Any, Iterable, Mapping

from gamepulse.providers.twitch import Snapshot
from gamepulse.streamer_opportunity import SnapshotFreshness


def _safe_url(value: str | None) -> str | None:
    if not value or not value.startswith(("https://", "http://")):
        return None
    return html.escape(value, quote=True)


def _art_markup(url: str | None, alt: str) -> str:
    safe_url = _safe_url(url)
    if safe_url:
        return f'<img class="gp-streamer-art" src="{safe_url}" alt="{html.escape(alt, quote=True)}" />'
    return '<div class="gp-streamer-placeholder" role="img" aria-label="Artwork unavailable">Artwork unavailable</div>'


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _text(value: Any, fallback: str = "Unavailable") -> str:
    if value is None or value == "":
        return fallback
    return html.escape(str(value), quote=True)


def _number(value: Any, fallback: str = "Unavailable") -> str:
    if value is None:
        return fallback
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return fallback


def _ratio(value: Any, fallback: str = "Unavailable") -> str:
    if value is None:
        return fallback
    try:
        return f"{float(value):,.1f}"
    except (TypeError, ValueError):
        return fallback


def _percent(value: Any, fallback: str = "Unavailable") -> str:
    if value is None:
        return fallback
    try:
        numeric = float(value)
        if abs(numeric) <= 1:
            numeric *= 100
        return f"{numeric:.0f}%"
    except (TypeError, ValueError):
        return fallback


def _source_mode(value: Any) -> str:
    mode = _get(value, "source_mode") or _get(value, "source") or _get(value, "mode") or "Unknown"
    return str(mode).replace("_", " ").title()


def _source_label(value: Any, fallback: str | None = None) -> str:
    source_name = _get(value, "source_name") or fallback or "Twitch provider"
    mode = _source_mode(value)
    observed_at = _get(value, "observed_at")
    suffix = f" · observed {observed_at}" if observed_at else ""
    return f"{mode} · {source_name}{suffix}"


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _history_values(history: Iterable[Any], field: str) -> list[float]:
    values: list[float] = []
    for row in history:
        raw = _get(row, field)
        try:
            if raw is not None:
                values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values


def _growth_from_history(history: tuple[Any, ...], days: int) -> float | None:
    if len(history) < 2:
        return None
    ordered = sorted(history, key=lambda row: _parse_time(_get(row, "observed_at")) or datetime.min.replace(tzinfo=timezone.utc))
    latest = ordered[-1]
    latest_value = _get(latest, "viewer_count")
    latest_time = _parse_time(_get(latest, "observed_at"))
    if latest_value is None or latest_time is None:
        return None
    target = latest_time.timestamp() - days * 86400
    prior = min(
        ordered[:-1],
        key=lambda row: abs((_parse_time(_get(row, "observed_at")) or latest_time).timestamp() - target),
    )
    prior_value = _get(prior, "viewer_count")
    try:
        if float(prior_value) <= 0:
            return None
        return (float(latest_value) - float(prior_value)) / float(prior_value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def render_streamer_hero(st, game, source_label: str = "Local prepared data") -> None:
    title = html.escape(str(game.name))
    release = html.escape(str(game.release_date)[:4]) if game.release_date else "Release year unavailable"
    price = "Price unavailable" if game.price_usd is None else ("Free" if game.price_usd == 0 else f"${game.price_usd:.2f}")
    review = f"{game.review_score:.0%} positive reviews" if game.review_score is not None else "Reviews unavailable"
    tags = "".join(f'<span class="gp-streamer-badge">{html.escape(item)}</span>' for item in (*game.genres[:2], *game.tags[:2]))
    markup = f"""
<section class="gp-streamer-shell gp-streamer-hero" aria-labelledby="gp-streamer-selected-game">
  <div>{_art_markup(game.header_image_url, f'{game.name} artwork')}</div>
  <div class="gp-streamer-hero-copy">
    <div class="gp-streamer-eyebrow">Selected game · {html.escape(source_label)}</div>
    <h2 id="gp-streamer-selected-game" class="gp-streamer-hero-title">{title}</h2>
    <div class="gp-streamer-muted">Released {release} · {html.escape(price)} · {html.escape(review)}</div>
    <div class="gp-streamer-badges" aria-label="Game categories">{tags or '<span class="gp-streamer-badge">Category data unavailable</span>'}</div>
  </div>
</section>
"""
    st.markdown(markup, unsafe_allow_html=True)


def render_snapshot_status(st, snapshot: Snapshot, freshness: SnapshotFreshness) -> None:
    provenance = f"Source: {_text(snapshot.source_name)} · observed {_text(snapshot.observed_at)}"
    if freshness.status == "live":
        st.success("Live Twitch data is connected.")
    elif freshness.status == "fresh_snapshot":
        st.info("Using a recent Twitch snapshot; results are directional until live credentials are connected.")
    else:
        st.warning(freshness.message)
    st.caption(f"{freshness.label} · {provenance}")


def render_opportunity_card(st, opportunity, featured: bool = False) -> None:
    raw_score = float(_get(opportunity, "score", 0) or 0)
    score = max(0, min(100, round(raw_score)))
    reasons = " · ".join(_text(item) for item in (_get(opportunity, "reasons", ()) or ())[:3]) or "Based on current Twitch category signals"
    cautions = " · ".join(_text(item) for item in (_get(opportunity, "cautions", ()) or ())[:3])
    confidence = _percent(_get(opportunity, "confidence_score"))
    trend = _text(_get(opportunity, "trend_direction"), "No trend signal")
    source = _text(_get(opportunity, "source_mode"), "Twitch observation")
    observed_at = _text(_get(opportunity, "observed_at"))
    caution_markup = f'<p class="gp-streamer-caution"><strong>Cautions:</strong> {cautions}</p>' if cautions else ""
    markup = f"""
<article class="gp-streamer-shell gp-streamer-card{' gp-streamer-card-featured' if featured else ''}" aria-label="Opportunity: {html.escape(str(_get(opportunity, 'name', 'Category')), quote=True)}">
  <div class="gp-streamer-card-copy">
    <p class="gp-streamer-card-title">{_text(_get(opportunity, 'name', 'Category'))}</p>
    <p><span class="gp-streamer-score">Opportunity {score}/100</span><span class="gp-streamer-band">{_text(_get(opportunity, 'score_band'))}</span></p>
    <p class="gp-streamer-confidence"><strong>Confidence:</strong> {confidence} · {_text(_get(opportunity, 'confidence_band'))}</p>
    <p class="gp-streamer-card-meta">Observed viewers {_number(_get(opportunity, 'viewer_count'))} · {_number(_get(opportunity, 'channel_count'))} channels · {_ratio(_get(opportunity, 'viewer_to_channel'))} viewers/channel</p>
    <p class="gp-streamer-card-meta"><strong>Trend:</strong> {trend} · <strong>Source:</strong> {source} · <strong>Observed:</strong> {observed_at}</p>
    <p class="gp-streamer-reasons"><strong>Reasons:</strong> {reasons}</p>
    {caution_markup}
  </div>
</article>
"""
    st.markdown(markup, unsafe_allow_html=True)


def render_opportunity_empty_state(st, message: str | None = None) -> None:
    st.info(message or "No Twitch categories are available in the current snapshot.")
    st.caption("Import an authorized snapshot or connect Twitch credentials, then refresh the page.")


def render_category_deep_dive(
    st,
    trend,
    *,
    history: tuple[Any, ...] = (),
    freshness_label: str | None = None,
    steam_metadata: Mapping[str, Any] | None = None,
) -> None:
    """Render observed category metrics and optional historical evidence."""

    history = tuple(history or ())
    name = _text(_get(trend, "name", "Selected category"))
    source = _text(freshness_label or _source_label(trend))
    viewers = _number(_get(trend, "viewer_count"))
    channels = _number(_get(trend, "channel_count"))
    ratio = _ratio(_get(trend, "viewer_to_channel"))
    historical_viewers = _history_values(history, "viewer_count")
    historical_channels = _history_values(history, "channel_count")
    historical_ratios = _history_values(history, "viewer_to_channel")
    average = mean(historical_viewers) if historical_viewers else _get(trend, "historical_average_viewers")
    peak = max(historical_viewers) if historical_viewers else _get(trend, "historical_peak_viewers")
    one_day = _growth_from_history(history, 1) if history else _get(trend, "one_day_growth")
    seven_day = _growth_from_history(history, 7) if history else _get(trend, "seven_day_growth")
    ratio_history = " → ".join(_ratio(value) for value in historical_ratios) if historical_ratios else "Unavailable"
    languages = _get(trend, "language_distribution") or {}
    if isinstance(languages, Mapping):
        language_text = ", ".join(f"{html.escape(str(key))}: {_number(value)}" for key, value in sorted(languages.items(), key=lambda item: str(item[0]).casefold())) or "Unavailable"
    else:
        language_text = _text(languages)
    observation_count = len(history) or _get(trend, "observation_count")
    concentration = f"Top 1 {_percent(_get(trend, 'top_one_viewer_share'))} · top 5 {_percent(_get(trend, 'top_five_viewer_share'))}"
    metrics = (
        ("Observed viewers", viewers),
        ("Observed channels", channels),
        ("Viewers per channel", ratio),
        ("Historical average", _number(average)),
        ("Historical peak", _number(peak)),
        ("One-day growth", _percent(one_day, "Unavailable")),
        ("Seven-day growth", _percent(seven_day, "Unavailable")),
        ("Viewer-to-channel history", ratio_history),
        ("Viewer concentration", concentration),
        ("Language distribution", language_text),
        ("Observation count", _number(observation_count)),
        ("Source freshness", source),
    )
    metric_markup = "".join(
        f'<div class="gp-streamer-metric"><span class="gp-streamer-metric-label">{html.escape(label)}</span><strong>{value}</strong></div>'
        for label, value in metrics
    )
    partial = bool(_get(trend, "partial_coverage", False))
    coverage_note = " Partial coverage." if partial else ""
    st.markdown(
        f"""
<section class="gp-streamer-shell gp-streamer-deep-dive">
  <div class="gp-streamer-section-heading"><h3>{name}</h3><span class="gp-streamer-source-badge">{source}</span></div>
  <p class="gp-streamer-observed-note">Twitch values below are observed totals, not complete Twitch totals.{html.escape(coverage_note)}</p>
  <div class="gp-streamer-metric-grid">{metric_markup}</div>
</section>
""",
        unsafe_allow_html=True,
    )

    if steam_metadata:
        steam_name = _text(steam_metadata.get("name") or steam_metadata.get("steam_name"))
        genres = ", ".join(_text(item) for item in steam_metadata.get("genres", ()) or ()) or "Unavailable"
        tags = ", ".join(_text(item) for item in steam_metadata.get("tags", ()) or ()) or "Unavailable"
        review = _percent(steam_metadata.get("review_score"), "Unavailable")
        st.markdown(
            f'<div class="gp-streamer-shell gp-streamer-steam"><strong>Verified Steam metadata</strong><br />{steam_name}<br /><span>Genres: {genres} · Tags: {tags} · Reviews: {review}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("No verified Steam mapping is available for this Twitch category.")

    if not history:
        st.info("Historical Twitch observations are unavailable for this category; current values are directional.")
        return
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.info("Trend chart is unavailable because Plotly is not installed.")
        return
    ordered = sorted(history, key=lambda row: _parse_time(_get(row, "observed_at")) or datetime.min.replace(tzinfo=timezone.utc))
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[_get(row, "observed_at") for row in ordered],
            y=[_get(row, "viewer_count") for row in ordered],
            mode="lines+markers",
            name="Observed viewers",
            line={"color": "#4C8DFF"},
        )
    )
    figure.update_layout(
        title="Observed viewer trend",
        height=300,
        margin={"l": 20, "r": 20, "t": 45, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#F4F7FC"},
    )
    if hasattr(st, "plotly_chart"):
        st.plotly_chart(figure, use_container_width=True)


def render_creator_landscape(st, snapshot: Snapshot) -> None:
    """Render current creators as context, never as developer promotion ranking."""

    st.info("Creator Landscape is informational and is not the developer promotion ranking.")
    st.caption(f"Source: {_text(snapshot.source_name)} · {_text(_source_mode(snapshot))} · observed {_text(snapshot.observed_at)}")
    if not snapshot.data:
        st.info("No creators were observed in this category at the selected observation time.")
        return
    for creator in snapshot.data:
        name = _text(_get(creator, "name", "Unnamed creator"))
        login = _get(creator, "login_name") or _get(creator, "streamer_login")
        image = _art_markup(_get(creator, "profile_image_url") or _get(creator, "profile_image"), f"{_get(creator, 'name', 'Creator')} profile image")
        if login:
            login_path = html.escape(str(login).strip("/"), quote=True)
            channel_url = f"https://www.twitch.tv/{login_path}"
            link = f'<a href="{channel_url}" target="_blank" rel="noopener">Open Twitch channel</a>'
        else:
            link = "Twitch link unavailable"
        avg = _get(creator, "average_viewers", _get(creator, "avg_viewers"))
        median = _get(creator, "median_viewers")
        primary_category = _get(creator, "primary_category") or _get(creator, "game_name")
        category_share = _get(creator, "primary_category_share")
        growth = _get(creator, "seven_day_growth", _get(creator, "growth_score"))
        confidence = _get(creator, "confidence_score")
        details = (
            ("Latest viewers", _number(_get(creator, "viewer_count"))),
            ("Average viewers", _number(avg)),
            ("Median viewers", _number(median)),
            ("Primary category", _text(primary_category)),
            ("Category share", _percent(category_share)),
            ("Language", _text(_get(creator, "language"))),
            ("Tier", _text(_get(creator, "channel_size_tier"))),
            ("Growth", _percent(growth)),
            ("Confidence", _percent(confidence)),
        )
        detail_markup = " · ".join(f"<strong>{html.escape(label)}:</strong> {value}" for label, value in details)
        st.markdown(
            f"""
<article class="gp-streamer-shell gp-streamer-creator">
  <div class="gp-streamer-creator-image">{image}</div>
  <div><p class="gp-streamer-card-title">{name}</p><p class="gp-streamer-card-meta">{detail_markup}</p><p>{link}</p></div>
</article>
""",
            unsafe_allow_html=True,
        )


def render_trending_streamers(st, snapshot: Snapshot) -> None:
    """Backward-compatible alias for callers that used the old section."""

    render_creator_landscape(st, snapshot)

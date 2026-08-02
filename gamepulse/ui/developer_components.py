"""Focused Streamlit rendering primitives for Developer Mode."""

from __future__ import annotations

import csv
import html
from io import StringIO
from typing import Any, Iterable, Mapping

from gamepulse.market_analysis import DeveloperOpportunity


def _safe_url(value: str | None) -> str | None:
    if not value or not value.startswith(("https://", "http://")):
        return None
    return html.escape(value, quote=True)


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


def _art_markup(url: str | None, alt: str) -> str:
    safe_url = _safe_url(url)
    if safe_url:
        return f'<img class="gp-developer-art" src="{safe_url}" alt="{html.escape(alt, quote=True)}" />'
    return '<div class="gp-developer-placeholder" role="img" aria-label="Artwork unavailable">Artwork unavailable</div>'


def _price_label(price: float | None) -> str:
    if price is None:
        return "Price unavailable"
    return "Free" if price == 0 else f"${price:.2f}"


def render_developer_hero(st, game, source_label: str = "Local prepared data") -> None:
    title = html.escape(str(game.name))
    release = html.escape(str(game.release_date)[:4]) if game.release_date else "Release year unavailable"
    review = f"{game.review_score:.0%} positive reviews" if game.review_score is not None else "Reviews unavailable"
    badges = "".join(
        f'<span class="gp-developer-badge">{html.escape(str(item))}</span>'
        for item in (*getattr(game, "genres", ())[:2], *getattr(game, "tags", ())[:2])
    )
    markup = f"""
<section class="gp-developer-shell gp-developer-hero" aria-labelledby="gp-developer-selected-game">
  <div>{_art_markup(getattr(game, "header_image_url", None), f'{game.name} artwork')}</div>
  <div class="gp-developer-hero-copy">
    <div class="gp-developer-eyebrow">Developer intelligence · {html.escape(source_label)}</div>
    <h2 id="gp-developer-selected-game" class="gp-developer-hero-title">{title}</h2>
    <div class="gp-developer-muted">Released {release} · {html.escape(_price_label(game.price_usd))} · {html.escape(review)}</div>
    <div class="gp-developer-badges" aria-label="Game categories">{badges or '<span class="gp-developer-badge">Category data unavailable</span>'}</div>
  </div>
</section>
"""
    st.markdown(markup, unsafe_allow_html=True)


def render_opportunity_summary(st, opportunity: DeveloperOpportunity) -> None:
    score = max(0, min(100, int(opportunity.score)))
    components = (
        ("Audience", opportunity.components.audience),
        ("Review health", opportunity.components.review_health),
        ("Momentum", opportunity.components.momentum),
        ("Creator fit", opportunity.components.creator_fit),
        ("Comparables", opportunity.components.comparable_coverage),
    )
    component_markup = "".join(
        f"""
        <div class="gp-developer-component">
          <div class="gp-developer-component-row"><span>{html.escape(label)}</span><span>{round(value * 100):.0f}/100</span></div>
          <div class="gp-developer-meter" aria-label="{html.escape(label)} signal {round(value * 100):.0f} out of 100"><div class="gp-developer-meter-fill" style="width:{max(0, min(100, value * 100)):.0f}%"></div></div>
        </div>
        """
        for label, value in components
    )
    reasons = "".join(f"<li>{html.escape(str(reason))}</li>" for reason in opportunity.reasons)
    markup = f"""
<section class="gp-developer-shell gp-developer-opportunity" aria-labelledby="gp-developer-opportunity-title">
  <div class="gp-developer-score">
    <div><div class="gp-developer-score-number">{score}/100</div><div class="gp-developer-score-label">Opportunity score</div><div class="gp-developer-score-band">{html.escape(opportunity.score_band)}</div></div>
  </div>
  <div>
    <h3 id="gp-developer-opportunity-title" class="gp-developer-opportunity-title">A decision-ready public-signal read</h3>
    <p class="gp-developer-opportunity-copy">This score makes the evidence visible so a developer can decide what to validate next. It is deliberately directional and never represents verified sales or downloads.</p>
    {component_markup}
    <ul class="gp-developer-reasons">{reasons}</ul>
    <p class="gp-developer-card-meta">{html.escape(opportunity.disclaimer)}</p>
  </div>
</section>
"""
    st.markdown(markup, unsafe_allow_html=True)


def render_signal_card(st, label: str, value: str, detail: str) -> None:
    markup = f"""
<article class="gp-developer-shell gp-developer-signal" aria-label="{html.escape(label, quote=True)}">
  <div class="gp-developer-signal-label">{html.escape(label)}</div>
  <div class="gp-developer-signal-value">{html.escape(value)}</div>
  <div class="gp-developer-signal-detail">{html.escape(detail)}</div>
</article>
"""
    st.markdown(markup, unsafe_allow_html=True)


def render_comparable_card(st, comparable) -> None:
    price = _price_label(getattr(comparable, "price_usd", comparable.get("price_usd") if isinstance(comparable, dict) else None))
    score = getattr(comparable, "review_score", comparable.get("review_score") if isinstance(comparable, dict) else None)
    review = "Reviews unavailable" if score is None else f"{score:.0%} positive reviews"
    name = getattr(comparable, "name", comparable.get("name", "Comparable game") if isinstance(comparable, dict) else "Comparable game")
    overlap = getattr(comparable, "comparable_overlap", comparable.get("comparable_overlap", comparable.get("overlap", 0)) if isinstance(comparable, dict) else 0)
    markup = f'<article class="gp-developer-shell gp-developer-card"><div class="gp-developer-card-title">{html.escape(str(name))}</div><div class="gp-developer-card-meta">{html.escape(price)} · {html.escape(review)} · overlap score {int(overlap)}</div></article>'
    st.markdown(markup, unsafe_allow_html=True)


def render_creator_fit_card(st, fit) -> None:
    name = _get(fit, "streamer_name") or _get(fit, "streamer_id", "Streamer")
    reasons = " · ".join(_text(item) for item in (_get(fit, "reasons", ()) or ())[:3]) or "Based on current creator signals"
    cautions = " · ".join(_text(item) for item in (_get(fit, "cautions", ()) or ())[:3]) or "None recorded"
    source_mode = _text(_get(fit, "source_mode"))
    source_name = _text(_get(fit, "source_name") or _get(fit, "source_mode"))
    observed_at = _text(_get(fit, "observed_at"))
    provenance_note = _get(fit, "provenance_note", "")
    profile_image = _safe_url(_get(fit, "profile_image_url"))
    image_markup = f'<img class="gp-developer-creator-image" src="{profile_image}" alt="{html.escape(str(name), quote=True)} profile image" />' if profile_image else '<div class="gp-developer-creator-placeholder">Profile image unavailable</div>'
    channel_url = _safe_url(_get(fit, "twitch_channel_url"))
    twitch_link = f'<a href="{channel_url}" target="_blank" rel="noopener">Open Twitch channel</a>' if channel_url else "Twitch link unavailable"
    components = _get(_get(fit, "components"), "values", {}) or {}
    component_labels = {
        "category_history_fit": "Category history fit",
        "similar_game_fit": "Similar-game fit",
        "audience_suitability": "Audience suitability",
        "consistency": "Consistency",
        "momentum": "Momentum",
        "language_fit": "Language fit",
        "discoverability": "Discoverability",
        "data_confidence": "Data confidence",
    }
    component_markup = "".join(
        f'<span class="gp-developer-component-chip"><strong>{html.escape(component_labels.get(key, key.replace("_", " ").title()))}:</strong> {_percent(value)}</span>'
        for key, value in components.items()
        if key in component_labels
    ) or '<span class="gp-developer-component-chip">Component detail unavailable</span>'
    markup = f"""
<article class="gp-developer-shell gp-developer-card gp-developer-creator-card" aria-label="Promotion recommendation: {html.escape(str(name), quote=True)}">
  <div class="gp-developer-creator-header"><div>{image_markup}</div><div><div class="gp-developer-card-title">{_text(name)}</div><div class="gp-developer-card-meta"><span class="gp-developer-fit-score">Promotion Fit Score {float(_get(fit, 'score', 0)):.1f}/100</span> · {_text(_get(fit, 'score_band'))}</div><div class="gp-developer-confidence">Confidence: {_percent(_get(fit, 'confidence_score'))} · {_text(_get(fit, 'confidence_band'))}</div></div></div>
  <div class="gp-developer-creator-metrics"><span>Average viewers: {_number(_get(fit, 'average_viewers'))}</span><span>Median viewers: {_number(_get(fit, 'median_viewers'))}</span><span>Peak viewers: {_number(_get(fit, 'peak_viewers'))}</span><span>Primary category: {_text(_get(fit, 'primary_category'))}</span><span>Category share: {_percent(_get(fit, 'primary_category_share'))}</span><span>Language: {_text(_get(fit, 'language'))}</span><span>Tier: {_text(_get(fit, 'channel_tier'))}</span><span>Growth: {_percent(_get(fit, 'seven_day_growth'), 'Unavailable - insufficient history')}</span><span>Growth interval: {_number(_get(fit, 'seven_day_growth_interval_hours'), 'Unavailable')}</span><span>Growth baseline: {_text(_get(fit, 'seven_day_growth_baseline_at'), 'Unavailable - insufficient history')}</span></div>
  <div class="gp-developer-component-chips">{component_markup}</div>
  <div class="gp-developer-card-copy"><strong>Strongest reasons:</strong> {reasons}</div>
  <div class="gp-developer-caution"><strong>Important cautions:</strong> {cautions}</div>
  <div class="gp-developer-card-meta">Source: {source_mode} · {source_name} · observed {observed_at} · {twitch_link}</div>
  {f'<div class="gp-developer-card-meta">Provenance: {_text(provenance_note)}</div>' if provenance_note else ''}
</article>
"""
    st.markdown(markup, unsafe_allow_html=True)


def render_creator_comparison(st, fits: Iterable[Any]) -> None:
    """Render a compact comparison of two or three selected public profiles."""

    selected = list(fits)[:3]
    if len(selected) < 2:
        st.info("Select two or three recommended streamers to compare them.")
        return
    fields = (
        ("Fit score", lambda fit: f"{float(_get(fit, 'score', 0)):.1f}/100"),
        ("Confidence", lambda fit: _percent(_get(fit, "confidence_score"))),
        ("Audience size", lambda fit: _number(_get(fit, "average_viewers"))),
        ("Category-history fit", lambda fit: _percent((_get(_get(fit, "components"), "values", {}) or {}).get("category_history_fit"))),
        ("Similar-game fit", lambda fit: _percent((_get(_get(fit, "components"), "values", {}) or {}).get("similar_game_fit"))),
        ("Audience suitability", lambda fit: _percent((_get(_get(fit, "components"), "values", {}) or {}).get("audience_suitability"))),
        ("Consistency", lambda fit: _percent((_get(_get(fit, "components"), "values", {}) or {}).get("consistency"))),
        ("Momentum", lambda fit: _percent((_get(_get(fit, "components"), "values", {}) or {}).get("momentum"))),
        ("Language fit", lambda fit: _percent((_get(_get(fit, "components"), "values", {}) or {}).get("language_fit"))),
        ("Discoverability", lambda fit: _percent((_get(_get(fit, "components"), "values", {}) or {}).get("discoverability"))),
    )
    header = "<tr><th>Measure</th>" + "".join(f"<th>{_text(_get(fit, 'streamer_name') or _get(fit, 'streamer_id'))}</th>" for fit in selected) + "</tr>"
    rows = "".join(
        "<tr><th>" + html.escape(label) + "</th>" + "".join(f"<td>{html.escape(str(formatter(fit)))}</td>" for fit in selected) + "</tr>"
        for label, formatter in fields
    )
    st.markdown(
        f'<section class="gp-developer-shell gp-developer-comparison"><h3>Streamer comparison</h3><table><thead>{header}</thead><tbody>{rows}</tbody></table></section>',
        unsafe_allow_html=True,
    )


def creator_fits_csv(fits: Iterable[Any]) -> str:
    """Serialize derived recommendation fields only; never raw provider payloads."""

    fieldnames = [
        "streamer_id", "streamer_name", "fit_score", "score_band", "confidence_score", "confidence_band",
        "average_viewers", "median_viewers", "peak_viewers", "primary_category", "primary_category_share",
        "language", "channel_tier", "seven_day_growth", "seven_day_growth_interval_hours", "seven_day_growth_baseline_at", "seven_day_growth_latest_at", "source_mode", "source_name", "observed_at",
        "partial_coverage", "provenance_note", "collection_ids", "twitch_channel_url",
        "reasons", "cautions", "category_history_fit", "similar_game_fit", "audience_suitability",
        "consistency", "momentum", "language_fit", "discoverability", "data_confidence",
    ]
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for fit in fits:
        components = _get(_get(fit, "components"), "values", {}) or {}
        row = {
            "streamer_id": _get(fit, "streamer_id", ""),
            "streamer_name": _get(fit, "streamer_name", ""),
            "fit_score": _get(fit, "score", ""),
            "score_band": _get(fit, "score_band", ""),
            "confidence_score": _get(fit, "confidence_score", ""),
            "confidence_band": _get(fit, "confidence_band", ""),
            "average_viewers": _get(fit, "average_viewers", ""),
            "median_viewers": _get(fit, "median_viewers", ""),
            "peak_viewers": _get(fit, "peak_viewers", ""),
            "primary_category": _get(fit, "primary_category", ""),
            "primary_category_share": _get(fit, "primary_category_share", ""),
            "language": _get(fit, "language", ""),
            "channel_tier": _get(fit, "channel_tier", ""),
            "seven_day_growth": _get(fit, "seven_day_growth", ""),
            "seven_day_growth_interval_hours": _get(fit, "seven_day_growth_interval_hours", ""),
            "seven_day_growth_baseline_at": _get(fit, "seven_day_growth_baseline_at", ""),
            "seven_day_growth_latest_at": _get(fit, "seven_day_growth_latest_at", ""),
            "source_mode": _get(fit, "source_mode", ""),
            "source_name": _get(fit, "source_name", ""),
            "observed_at": _get(fit, "observed_at", ""),
            "partial_coverage": _get(fit, "partial_coverage", ""),
            "provenance_note": _get(fit, "provenance_note", ""),
            "collection_ids": "; ".join(str(item) for item in (_get(fit, "collection_ids", ()) or ())),
            "twitch_channel_url": _get(fit, "twitch_channel_url", ""),
            "reasons": "; ".join(str(item) for item in (_get(fit, "reasons", ()) or ())),
            "cautions": "; ".join(str(item) for item in (_get(fit, "cautions", ()) or ())),
        }
        row.update({key: components.get(key, "") for key in fieldnames if key in components})
        writer.writerow(row)
    return output.getvalue()

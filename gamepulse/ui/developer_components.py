"""Focused Streamlit rendering primitives for Developer Mode."""

from __future__ import annotations

import html

from gamepulse.market_analysis import DeveloperOpportunity


def _safe_url(value: str | None) -> str | None:
    if not value or not value.startswith(("https://", "http://")):
        return None
    return html.escape(value, quote=True)


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
    reasons = " · ".join(str(item) for item in getattr(fit, "reasons", ())[:3]) or "Based on current creator signals"
    markup = f'<article class="gp-developer-shell gp-developer-card"><div class="gp-developer-card-title">{html.escape(str(fit.streamer_id))}</div><div class="gp-developer-card-meta"><span style="color:#6EA8FF;font-weight:750">Fit {float(fit.score):.0f}/100</span> · {html.escape(str(fit.score_band))}</div><div class="gp-developer-card-copy">{html.escape(reasons)}</div></article>'
    st.markdown(markup, unsafe_allow_html=True)

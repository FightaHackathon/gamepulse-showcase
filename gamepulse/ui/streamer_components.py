"""Focused Streamlit rendering primitives for Streamer Mode."""

from __future__ import annotations

import html

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
    provenance = f"Source: {snapshot.source_name} · observed {snapshot.observed_at}"
    if freshness.status == "live":
        st.success("Live Twitch data is connected.")
    elif freshness.status == "fresh_snapshot":
        st.info("Using a recent Twitch snapshot; results are directional until live credentials are connected.")
    else:
        st.warning(freshness.message)
    st.caption(f"{freshness.label} · {provenance}")


def render_opportunity_card(st, opportunity, featured: bool = False) -> None:
    score = max(0, min(100, round(float(opportunity.score) * 100)))
    reasons = " · ".join(html.escape(str(item)) for item in opportunity.reasons[:3]) or "Based on current Twitch category signals"
    markup = f"""
<article class="gp-streamer-shell gp-streamer-card{' gp-streamer-card-featured' if featured else ''}" aria-label="Opportunity: {html.escape(str(opportunity.name), quote=True)}">
  <div class="gp-streamer-card-copy">
    <p class="gp-streamer-card-title">{html.escape(str(opportunity.name))}</p>
    <p><span class="gp-streamer-score">Opportunity {score}/100</span><span class="gp-streamer-band">{html.escape(str(opportunity.score_band))}</span></p>
    <p class="gp-streamer-card-meta">Observed viewers {int(opportunity.viewer_count):,} · {int(opportunity.channel_count):,} channels · {float(opportunity.viewer_to_channel):.1f} viewers/channel</p>
    <p class="gp-streamer-reasons">{reasons}</p>
  </div>
</article>
"""
    st.markdown(markup, unsafe_allow_html=True)


def render_opportunity_empty_state(st) -> None:
    st.info("No Twitch categories are available in the current snapshot.")
    st.caption("Import an authorized snapshot or connect Twitch credentials, then refresh the page.")


def render_trending_streamers(st, snapshot: Snapshot) -> None:
    """Show the creators currently observed in the chosen Twitch category."""
    st.caption(f"Source: {snapshot.source_name} · observed {snapshot.observed_at}")
    if not snapshot.data:
        st.info("No live creators were found for this category in the current snapshot.")
        return
    for creator in snapshot.data[:5]:
        tags = ", ".join(str(item) for item in creator.tags[:3])
        details = [
            f"{int(creator.viewer_count):,} viewers",
            creator.channel_size_tier.replace("-", " ").title(),
        ]
        if creator.language:
            details.append(creator.language.upper())
        if tags:
            details.append(tags)
        st.markdown(
            f"**{html.escape(str(creator.name))}** · {html.escape(' · '.join(details))}",
            unsafe_allow_html=True,
        )

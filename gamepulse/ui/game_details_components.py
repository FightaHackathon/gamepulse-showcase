"""Streamlit primitives for an on-demand game specification and review catalogue."""

from datetime import datetime, timezone

from gamepulse.game_details import GameDetails, ReviewRecord


def _date_label(created_at_unix: int | None) -> str:
    if created_at_unix is None:
        return "Date unavailable"
    try:
        return datetime.fromtimestamp(created_at_unix, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return "Date unavailable"


def _review_label(review: ReviewRecord) -> str:
    sentiment = "Recommended" if review.recommended else "Not recommended" if review.recommended is False else "No sentiment"
    playtime = f"{review.author_playtime_minutes:,} min played" if review.author_playtime_minutes is not None else "Playtime unavailable"
    return f"{sentiment} · {_date_label(review.created_at_unix)} · {playtime}"


def render_game_details(st, details: GameDetails) -> None:
    """Render metadata and a bounded newest-review catalogue using Streamlit primitives."""
    game = details.game
    catalogue = details.review_catalogue
    st.subheader(f"{game.name} details")
    if game.release_date:
        st.caption(f"Released {game.release_date}")
    st.link_button("Open on Steam", details.steam_store_url, use_container_width=True)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Price", "Free" if game.price_usd == 0 else f"${game.price_usd:.2f}" if game.price_usd is not None else "Unavailable")
    metric_columns[1].metric("Review score", f"{catalogue.review_score:.0%}" if catalogue.review_score is not None else "Unavailable")
    metric_columns[2].metric("Reviews", f"{catalogue.review_count:,}")
    metric_columns[3].metric("Peak CCU", f"{game.peak_ccu:,}" if game.peak_ccu is not None else "Unavailable")

    st.write("**Genres:** " + (", ".join(game.genres) or "Unavailable"))
    st.write("**Tags:** " + (", ".join(game.tags) or "Unavailable"))
    platforms = [label for label, enabled in (("Windows", game.windows), ("macOS", game.mac), ("Linux", game.linux)) if enabled]
    st.write("**Platforms:** " + (", ".join(platforms) or "Unavailable"))
    if game.owners_low is not None or game.owners_high is not None:
        low = f"{game.owners_low:,}" if game.owners_low is not None else "?"
        high = f"{game.owners_high:,}" if game.owners_high is not None else "?"
        st.write(f"**Estimated owners:** {low}–{high}")

    if details.analysis.positive_themes:
        st.caption("Positive themes · " + " · ".join(details.analysis.positive_themes))
    if details.analysis.negative_themes:
        st.caption("Critical themes · " + " · ".join(details.analysis.negative_themes))

    st.subheader("Review catalogue")
    st.caption(
        f"Showing {len(catalogue.reviews):,} newest public reviews · "
        f"{catalogue.recommended_count:,} recommended · {catalogue.not_recommended_count:,} not recommended"
    )
    if not catalogue.reviews:
        st.info("No review text is available for this game in the prepared catalogue.")
        return

    for review in catalogue.reviews:
        with st.expander(_review_label(review)):
            st.write(review.review_text)
            st.caption(f"Helpful votes: {review.helpful_votes:,} · Funny votes: {review.funny_votes:,}")

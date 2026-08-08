"""Focused Streamlit rendering primitives for Player Mode."""

import html
from dataclasses import dataclass
from typing import Literal

from gamepulse.catalog import PreferenceOptions
from gamepulse.config import Settings
from gamepulse.player_session import PlayerProfileSession
from gamepulse.providers.steam import PlayerLibrary
from gamepulse.recommendations import PlayerPreferences, Recommendation


PersonalizationActionKind = Literal["none", "analyze", "refresh", "clear"]


@dataclass(frozen=True)
class PersonalizationAction:
    kind: PersonalizationActionKind = "none"
    profile_input: str = ""


def _safe_url(value: str | None) -> str | None:
    if not value or not value.startswith(("https://", "http://")):
        return None
    return html.escape(value, quote=True)


def _price_label(price: float | None) -> str:
    if price is None:
        return "Price unavailable"
    return "Free" if price == 0 else f"${price:.2f}"


def _platform_labels(item) -> tuple[str, ...]:
    labels = []
    for label, field in (("Windows", "windows"), ("macOS", "mac"), ("Linux", "linux")):
        value = getattr(item, field, None)
        if value:
            labels.append(label)
    return tuple(labels) or ("Platform data unavailable",)


def _library_is_complete(library: PlayerLibrary | None) -> bool:
    return bool(library and (library.complete or library.source_name == "Steam Web API"))


def _profile_playtime_caption(library: PlayerLibrary) -> str:
    total_minutes = sum(max(0, int(item.get("playtime_forever") or 0)) for item in library.games if isinstance(item, dict))
    return f"Profile signal · {len(library.games):,} games analyzed · {total_minutes / 60:,.1f} hours tracked"


def _top_played_caption(library: PlayerLibrary, limit: int = 5) -> str:
    played = [
        (str(item.get("name") or f"Steam App {item.get('appid', '?')}"), max(0, int(item.get("playtime_forever") or 0)))
        for item in library.games
        if isinstance(item, dict) and int(item.get("playtime_forever") or 0) > 0
    ]
    played.sort(key=lambda item: (-item[1], item[0].casefold()))
    if not played:
        return "Most played · playtime unavailable"
    return "Most played · " + " · ".join(f"{name} ({minutes / 60:,.1f}h)" for name, minutes in played[:limit])


def profile_library_rows(library: PlayerLibrary) -> list[dict[str, object]]:
    """Build a display-ready row for every owned game returned by Steam."""
    rows = []
    for item in library.games:
        if not isinstance(item, dict):
            continue
        try:
            app_id = int(item.get("appid"))
        except (TypeError, ValueError):
            continue
        playtime = max(0, int(item.get("playtime_forever") or 0))
        recent = max(0, int(item.get("playtime_2weeks") or 0))
        rows.append(
            {
                "Game": str(item.get("name") or f"Steam App {app_id}"),
                "App ID": app_id,
                "Hours played": round(playtime / 60, 1),
                "Recent hours": round(recent / 60, 1),
            }
        )
    rows.sort(key=lambda row: (-float(row["Hours played"]), str(row["Game"]).casefold()))
    return rows


def _art_markup(url: str | None, alt: str, class_name: str = "gp-game-art") -> str:
    safe_url = _safe_url(url)
    if safe_url:
        return f'<img class="{class_name}" src="{safe_url}" alt="{html.escape(alt, quote=True)}" />'
    return '<div class="gp-game-art-placeholder" role="img" aria-label="Artwork unavailable">Artwork unavailable</div>'


def render_player_hero(st, game, source_label: str = "Local prepared data") -> None:
    """Render the selected game's visual anchor and provenance."""
    title = html.escape(str(game.name))
    release = html.escape(str(game.release_date)[:4]) if game.release_date else "Release year unavailable"
    platforms = "".join(
        f'<span class="gp-player-badge">{html.escape(label)}</span>'
        for label in _platform_labels(game)
    )
    metadata = " · ".join(
        item
        for item in (
            f"Released {release}" if game.release_date else None,
            _price_label(game.price_usd),
            f"{game.review_score:.0%} positive reviews" if game.review_score is not None else "Reviews unavailable",
        )
        if item
    )
    markup = f"""
<section class="gp-player-shell gp-player-hero" aria-labelledby="gp-player-selected-game">
  <div>{_art_markup(game.header_image_url, f'{game.name} artwork', 'gp-player-hero-art')}</div>
  <div class="gp-player-hero-copy">
    <div class="gp-player-eyebrow">Selected game · {html.escape(source_label)}</div>
    <h2 id="gp-player-selected-game" class="gp-player-hero-title">{title}</h2>
    <div class="gp-player-muted">{html.escape(metadata)}</div>
    <div class="gp-player-badges" aria-label="Supported platforms">{platforms}</div>
  </div>
</section>
"""
    st.markdown(markup, unsafe_allow_html=True)


def render_personalization(st, profile_state: PlayerProfileSession, settings: Settings, options: PreferenceOptions) -> PersonalizationAction:
    """Render the optional public Steam connector and return a user action."""
    st.subheader("Personalize your recommendations")
    if profile_state.status in {"private", "rate_limited", "unavailable"}:
        st.warning(profile_state.message)
    elif profile_state.status == "connected":
        count = len(profile_state.owned_app_ids)
        library = profile_state.library
        scope = "public library games" if library is None or _library_is_complete(library) else "recent public games"
        if library:
            st.caption(_profile_playtime_caption(library))
            st.caption(_top_played_caption(library))
            with st.expander(f"View all {len(library.games):,} analyzed games"):
                rows = profile_library_rows(library)
                if rows:
                    st.dataframe(rows, hide_index=True, use_container_width=True)
                else:
                    st.info("No owned-game rows were returned by Steam.")
        st.success(f"Connected · {count:,} {scope} analyzed for this session.")
        inferred = profile_state.preferences
        chips = [*(f"Tag: {item}" for item in inferred.preferred_tags[:4]), *(f"Genre: {item}" for item in inferred.preferred_genres[:3])]
        if chips:
            st.caption("Inferred preferences · " + " · ".join(chips))

    if profile_state.status == "connected" and profile_state.library:
        source_name = profile_state.library.source_name
        if _library_is_complete(profile_state.library):
            st.caption(f"Source: {source_name}; all visible games and recorded playtime were analyzed.")
        else:
            st.caption(f"Source: {source_name}; recent games only.")
    elif profile_state.status != "connected" and not settings.steam_enabled:
        st.info("Steam Web API key is not configured; public-profile analysis is ready and manual mode remains available.")
        st.caption("Without a key, GamePulse reads the public Steam games page for all visible games and playtime, then falls back to recent profile cards. Add STEAM_WEB_API_KEY for the official API path.")

    with st.form("gp_player_steam_form", clear_on_submit=False):
        profile = st.text_input(
            "Public Steam profile URL or SteamID",
            value=profile_state.profile_input,
            key="gp_player_steam_profile",
            help="Only public profile data is read. GamePulse uses public game rows and playtime; no password or cookie is requested.",
        )
        st.caption("Public-page mode reads all visible owned games and recorded hours when available; the official Web API is used when configured. The analysis stays in this browser session.")
        submit_label = "Analyze public library" if settings.steam_enabled else "Analyze public profile"
        submitted = st.form_submit_button(
            submit_label,
            type="primary",
            use_container_width=True,
        )
    if submitted:
        return PersonalizationAction("analyze", profile.strip())

    if profile_state.status == "connected":
        refresh = st.button("Refresh library", key="gp_player_refresh", use_container_width=True)
        clear = st.button("Clear Steam connection", key="gp_player_clear", use_container_width=True)
        if refresh:
            return PersonalizationAction("refresh", profile.strip())
        if clear:
            return PersonalizationAction("clear")
    return PersonalizationAction()


def _reset_filter_state(st) -> None:
    st.session_state["gp_player_discovery_mode"] = "Best matches"
    st.session_state["gp_player_os"] = "Any"
    st.session_state["gp_player_price_ceiling"] = "Any price"
    st.session_state["gp_player_tags"] = []
    st.session_state["gp_player_genres"] = []


def render_player_filters(st, options: PreferenceOptions, initial: PlayerPreferences | None = None) -> PlayerPreferences:
    """Render bounded manual controls and return the current preference contract."""
    initial = initial or PlayerPreferences()
    st.subheader("Discovery controls")
    st.button("Reset filters", key="gp_player_reset", on_click=_reset_filter_state)
    discovery_label = st.radio(
        "Discovery",
        ["Best matches", "Hidden gems"],
        index=0,
        key="gp_player_discovery_mode",
        horizontal=True,
        help="Best matches prioritize fit. Hidden gems down-rank very large audiences.",
    )
    operating_system = st.selectbox("Operating system", ["Any", "Windows", "macOS", "Linux"], key="gp_player_os")
    price_ceiling = st.selectbox(
        "Price ceiling",
        ["Any price", "Free", "$10 or less", "$20 or less", "$40 or less", "$60 or less", "$100 or less"],
        key="gp_player_price_ceiling",
    )
    price_map = {"Any price": None, "Free": 0.0, "$10 or less": 10.0, "$20 or less": 20.0, "$40 or less": 40.0, "$60 or less": 60.0, "$100 or less": 100.0}
    selected_tags = st.multiselect(
        "Preferred tags",
        list(options.tags),
        default=[item for item in initial.preferred_tags if item in options.tags],
        key="gp_player_tags",
        placeholder="Choose tags",
    )
    selected_genres = st.multiselect(
        "Preferred genres",
        list(options.genres),
        default=[item for item in initial.preferred_genres if item in options.genres],
        key="gp_player_genres",
        placeholder="Choose genres",
    )
    return PlayerPreferences(
        preferred_tags=tuple(dict.fromkeys(str(item).casefold() for item in selected_tags)),
        preferred_genres=tuple(dict.fromkeys(str(item).casefold() for item in selected_genres)),
        max_price_usd=price_map[price_ceiling],
        operating_system=None if operating_system == "Any" else operating_system,
        discovery_mode="hidden_gems" if discovery_label == "Hidden gems" else "best_matches",
    )


def render_recommendation_card(st, recommendation: Recommendation, featured: bool = False) -> None:
    reasons = " · ".join(html.escape(item) for item in recommendation.reasons) or "Based on the selected game's catalog signals"
    meta = " · ".join(
        item
        for item in (
            recommendation.release_year,
            _price_label(recommendation.price_usd),
            f"{recommendation.review_score:.0%} positive" if recommendation.review_score is not None else "Reviews unavailable",
        )
        if item
    )
    audience = ""
    if recommendation.owners_high is not None:
        audience = f" · Est. audience {recommendation.owners_high:,}+"
    platforms = " · ".join(_platform_labels(recommendation))
    link = _safe_url(recommendation.steam_store_url)
    link_markup = f'<a class="gp-player-card-link" href="{link}" target="_blank" rel="noreferrer">View on Steam</a>' if link else '<span class="gp-player-muted">Steam link unavailable</span>'
    featured_class = " gp-player-card-featured" if featured else ""
    markup = f"""
<article class="gp-player-card{featured_class}" aria-label="Recommendation: {html.escape(recommendation.name, quote=True)}">
  {_art_markup(recommendation.header_image_url, f'{recommendation.name} artwork')}
  <div class="gp-player-card-copy">
    <p class="gp-player-card-title">{html.escape(recommendation.name)}</p>
    <p><span class="gp-player-match">Match {recommendation.match_score}/100</span><span class="gp-player-match-band">{html.escape(recommendation.score_band)}</span></p>
    <p class="gp-player-card-meta">{html.escape(meta)}{html.escape(audience)} · {html.escape(platforms)}</p>
    <p class="gp-player-reasons">{reasons}</p>
    <p>{link_markup}</p>
  </div>
</article>
"""
    st.markdown(markup, unsafe_allow_html=True)


def render_recommendation_empty_state(st, preferences: PlayerPreferences) -> None:
    st.info("No games match all active filters.")
    if preferences.discovery_mode == "hidden_gems":
        st.caption("Try Best matches or broaden the price, platform, or preference filters.")
    else:
        st.caption("Try broadening the price, platform, or preference filters.")

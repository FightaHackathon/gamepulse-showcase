"""Session-only state for optional public Steam personalization."""

from dataclasses import dataclass
from typing import Literal

from gamepulse.player_profile import infer_preferences
from gamepulse.providers.steam import PlayerLibrary, SteamProvider, SteamProviderError
from gamepulse.recommendations import PlayerPreferences


ProfileStatus = Literal[
    "disconnected",
    "loading",
    "connected",
    "private",
    "rate_limited",
    "unavailable",
]


@dataclass(frozen=True)
class PlayerProfileSession:
    status: ProfileStatus
    profile_input: str = ""
    steam_id: str | None = None
    library: PlayerLibrary | None = None
    owned_app_ids: frozenset[int] = frozenset()
    preferences: PlayerPreferences = PlayerPreferences()
    message: str = ""


def empty_profile_session() -> PlayerProfileSession:
    return PlayerProfileSession(status="disconnected")


def _error_status(error: BaseException) -> tuple[ProfileStatus, str]:
    text = str(error).casefold()
    if "private" in text:
        return "private", "Game Details are private."
    if "rate limit" in text or "429" in text:
        return "rate_limited", "Steam is temporarily rate limited."
    return "unavailable", "Steam personalization is temporarily unavailable."


def analyze_public_profile(profile_input: str, provider: SteamProvider, catalog) -> PlayerProfileSession:
    """Resolve and analyze one public profile; callers decide when to refresh."""
    value = profile_input.strip()
    if not value:
        return empty_profile_session()

    try:
        steam_id = provider.resolve_profile(value)
        library = provider.get_library(steam_id)
        preferences = infer_preferences(library, catalog)
    except (SteamProviderError, RuntimeError, ValueError, KeyError) as error:
        status, message = _error_status(error)
        return PlayerProfileSession(status=status, profile_input=value, message=message)

    owned_app_ids = frozenset(
        int(item["appid"])
        for item in library.games
        if isinstance(item, dict) and str(item.get("appid", "")).isdigit()
    )
    return PlayerProfileSession(
        status="connected",
        profile_input=value,
        steam_id=library.steam_id or steam_id,
        library=library,
        owned_app_ids=owned_app_ids,
        preferences=preferences,
        message="Connected to public Steam library.",
    )

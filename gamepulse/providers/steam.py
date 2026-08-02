"""Public Steam profile/library connector; never handles Steam passwords."""

import json
import re
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerLibrary:
    steam_id: str
    games: tuple[dict, ...]


class SteamProviderError(RuntimeError):
    """Recoverable Steam API/provider failure suitable for UI fallback."""


def parse_steam_profile(value: str) -> tuple[str | None, str | None]:
    value = value.strip()
    numeric = re.search(r"/profiles/(\d{17})(?:/|$)", value)
    if numeric:
        return numeric.group(1), None
    vanity = re.search(r"/id/([A-Za-z0-9_-]+)(?:/|$)", value)
    if vanity:
        return None, vanity.group(1)
    if re.fullmatch(r"\d{17}", value):
        return value, None
    raise ValueError("enter a Steam profile URL, vanity URL, or 17-digit SteamID")


class SteamProvider:
    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def _get(self, interface: str, method: str, params: dict[str, str]) -> dict:
        if not self.api_key:
            raise RuntimeError("Steam Web API key is not configured")
        query = urllib.parse.urlencode({"key": self.api_key, "format": "json", **params})
        try:
            with urllib.request.urlopen(f"https://api.steampowered.com/{interface}/{method}/v1/?{query}", timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429:
                raise SteamProviderError("Steam API rate limit reached; try again later") from exc
            if exc.code in {401, 403}:
                raise SteamProviderError("Steam API access was denied; check the key or profile privacy") from exc
            raise SteamProviderError(f"Steam API request failed ({exc.code})") from exc
        except URLError as exc:
            raise SteamProviderError("Steam API is unavailable; using manual preferences") from exc

    def resolve_profile(self, profile: str) -> str:
        steam_id, vanity = parse_steam_profile(profile)
        if steam_id:
            return steam_id
        payload = self._get("ISteamUser", "ResolveVanityURL", {"vanityurl": vanity or ""})
        resolved = payload.get("response", {}).get("steamid")
        if not resolved:
            raise ValueError("Steam could not resolve that profile")
        return str(resolved)

    def get_library(self, steam_id: str) -> PlayerLibrary:
        payload = self._get("IPlayerService", "GetOwnedGames", {"steamid": steam_id, "include_appinfo": "1", "include_played_free_games": "1"})
        response = payload.get("response", {})
        if "games" not in response and response.get("game_count") is None:
            raise SteamProviderError("Steam Game Details are private or unavailable")
        games = tuple(response.get("games", []))
        return PlayerLibrary(steam_id, games)

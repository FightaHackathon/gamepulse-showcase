"""Public Steam profile/library connector; never handles Steam passwords."""

import json
import re
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass(frozen=True)
class PlayerLibrary:
    steam_id: str
    games: tuple[dict, ...]
    source_name: str = "Steam Web API"
    complete: bool = False


class SteamProviderError(RuntimeError):
    """Recoverable Steam API/provider failure suitable for UI fallback."""


class _PublicProfilePageParser(HTMLParser):
    """Extract the recent-game cards rendered on a public Steam profile page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.games: list[dict] = []
        self._current: dict[str, str] | None = None
        self._recent_depth = 0
        self._capture: str | None = None
        self._capture_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        attributes = dict(attrs)
        classes = set(str(attributes.get("class", "")).split())
        if tag == "div" and "recent_game" in classes:
            if self._current is not None:
                self._finish_current()
            self._current = {}
            self._recent_depth = 1
            return
        if self._current is None:
            return
        if tag == "div":
            self._recent_depth += 1
        if tag == "a":
            match = re.search(r"/app/(\d+)(?:/|$)", str(attributes.get("href", "")))
            if match and "appid" not in self._current:
                self._current["appid"] = match.group(1)
        if tag == "div" and "game_name" in classes:
            self._capture = "name"
            self._capture_parts = []
        elif tag == "div" and "game_info_details" in classes:
            self._capture = "details"
            self._capture_parts = []

    def handle_data(self, data: str):
        if self._current is not None and self._capture:
            self._capture_parts.append(data)

    def handle_endtag(self, tag: str):
        if tag != "div" or self._current is None:
            return
        if self._capture:
            self._current[self._capture] = " ".join(" ".join(self._capture_parts).split())
            self._capture = None
            self._capture_parts = []
        self._recent_depth -= 1
        if self._recent_depth <= 0:
            self._finish_current()

    def _finish_current(self):
        current = self._current or {}
        appid = current.get("appid")
        if appid:
            details = current.get("details", "")
            hours_match = re.search(r"([\d,.]+)\s+hrs?\s+on\s+record", details, re.IGNORECASE)
            hours = float(hours_match.group(1).replace(",", "")) if hours_match else 0.0
            self.games.append(
                {
                    "appid": int(appid),
                    "name": current.get("name") or f"Steam App {appid}",
                    "playtime_forever": round(max(0.0, hours) * 60),
                    "playtime_2weeks": 0,
                }
            )
        self._current = None
        self._recent_depth = 0
        self._capture = None
        self._capture_parts = []


class _PublicGamesPageParser(HTMLParser):
    """Extract all game rows and recorded playtime from the public games tab."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.games: list[dict] = []
        self._current: dict[str, object] | None = None
        self._row_depth = 0
        self._capture: str | None = None
        self._capture_depth = 0
        self._capture_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        attributes = dict(attrs)
        classes = set(str(attributes.get("class", "")).split())
        if self._current is None:
            if tag == "div" and "gameListRow" in classes:
                appid = re.search(r"\d+", str(attributes.get("data-appid", "")))
                if appid:
                    self._current = {"appid": int(appid.group(0)), "name": "", "values": []}
                    self._row_depth = 1
            return

        if tag == "div":
            self._row_depth += 1
        if tag == "div" and "gameListRowItemName" in classes:
            self._capture = "name"
            self._capture_depth = self._row_depth
            self._capture_parts = []
        elif tag == "div" and "gameListRowItemValue" in classes:
            self._capture = "value"
            self._capture_depth = self._row_depth
            self._capture_parts = []

    def handle_data(self, data: str):
        if self._current is not None and self._capture:
            self._capture_parts.append(data)

    def handle_endtag(self, tag: str):
        if tag != "div" or self._current is None:
            return
        if self._capture and self._row_depth == self._capture_depth:
            value = " ".join(" ".join(self._capture_parts).split())
            if self._capture == "name":
                self._current["name"] = value
            else:
                values = self._current.setdefault("values", [])
                if isinstance(values, list):
                    values.append(value)
            self._capture = None
            self._capture_parts = []
        if self._row_depth <= 1:
            self._finish_current()
            return
        self._row_depth -= 1

    def _finish_current(self):
        current = self._current or {}
        appid = current.get("appid")
        if appid:
            values = current.get("values", [])
            details = " ".join(str(value) for value in values) if isinstance(values, list) else ""
            hours_match = re.search(r"([\d,.]+)\s+hrs?\s+on\s+record", details, re.IGNORECASE)
            hours = float(hours_match.group(1).replace(",", "")) if hours_match else 0.0
            self.games.append(
                {
                    "appid": int(appid),
                    "name": str(current.get("name") or f"Steam App {appid}"),
                    "playtime_forever": round(max(0.0, hours) * 60),
                    "playtime_2weeks": 0,
                }
            )
        self._current = None
        self._row_depth = 0
        self._capture = None
        self._capture_parts = []


def parse_steam_profile(value: str) -> tuple[str | None, str | None]:
    value = value.strip()
    numeric = re.search(r"(?:^|/)profiles/(\d{17})(?=$|[/?#])", value)
    if numeric:
        return numeric.group(1), None
    vanity = re.search(r"(?:^|/)id/([A-Za-z0-9_-]+)(?=$|[/?#])", value)
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

    @staticmethod
    def _profile_id_from_page(page: str) -> str | None:
        match = re.search(r"[\"']steamid[\"']\s*:\s*[\"'](\d{17})[\"']", page)
        return match.group(1) if match else None

    @staticmethod
    def _fetch_profile_page(url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": "GamePulse prototype/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.read().decode("utf-8", "replace")
        except HTTPError as exc:
            if exc.code == 429:
                raise SteamProviderError("Steam profile page rate limit reached; try again later") from exc
            raise SteamProviderError(f"Steam profile page request failed ({exc.code})") from exc
        except URLError as exc:
            raise SteamProviderError("Steam profile page is unavailable; using manual preferences") from exc

    def _resolve_public_vanity(self, vanity: str) -> str:
        safe_vanity = urllib.parse.quote(vanity, safe="")
        page = self._fetch_profile_page(f"https://steamcommunity.com/id/{safe_vanity}/")
        resolved = self._profile_id_from_page(page)
        if not resolved:
            raise ValueError("Steam could not resolve that public profile")
        return resolved

    def _get_public_profile_library(self, steam_id: str) -> PlayerLibrary:
        page = self._fetch_profile_page(f"https://steamcommunity.com/profiles/{steam_id}/")
        resolved = self._profile_id_from_page(page)
        if not resolved:
            raise SteamProviderError("Steam profile is not publicly visible or could not be found")

        try:
            games_page = self._fetch_profile_page(f"https://steamcommunity.com/profiles/{resolved}/games/?tab=all")
        except SteamProviderError:
            games_page = ""
        games_parser = _PublicGamesPageParser()
        games_parser.feed(games_page)
        if games_parser.games:
            return PlayerLibrary(resolved, tuple(games_parser.games), "Public Steam games page", True)

        parser = _PublicProfilePageParser()
        parser.feed(page)
        if not parser.games:
            raise SteamProviderError("Steam Game Details are private or no recent games are publicly visible")
        return PlayerLibrary(resolved, tuple(parser.games), "Public Steam profile page", False)

    def resolve_profile(self, profile: str) -> str:
        steam_id, vanity = parse_steam_profile(profile)
        if steam_id:
            return steam_id
        if not self.api_key:
            return self._resolve_public_vanity(vanity or "")
        payload = self._get("ISteamUser", "ResolveVanityURL", {"vanityurl": vanity or ""})
        resolved = payload.get("response", {}).get("steamid")
        if not resolved:
            raise ValueError("Steam could not resolve that profile")
        return str(resolved)

    def get_library(self, steam_id: str) -> PlayerLibrary:
        if not self.api_key:
            return self._get_public_profile_library(steam_id)
        payload = self._get("IPlayerService", "GetOwnedGames", {"steamid": steam_id, "include_appinfo": "1", "include_played_free_games": "1"})
        response = payload.get("response", {})
        if "games" not in response and response.get("game_count") is None:
            raise SteamProviderError("Steam Game Details are private or unavailable")
        games = tuple(response.get("games", []))
        return PlayerLibrary(steam_id, games, "Steam Web API", True)

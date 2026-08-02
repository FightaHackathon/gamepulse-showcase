"""Twitch Helix provider with a bounded, clearly labelled demo fallback."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import HTTPError


@dataclass(frozen=True)
class GameTrend:
    game_id: str
    name: str
    viewer_count: int
    channel_count: int
    growth_score: float = 0.0
    tags: tuple[str, ...] = ()
    rank: int | None = None
    viewer_to_channel: float = 0.0
    top_one_viewer_share: float = 0.0
    top_five_viewer_share: float = 0.0
    average_stream_age_seconds: float | None = None
    language_distribution: tuple[tuple[str, int], ...] = ()
    contributing_stream_rows: int = 0
    pages_collected: int = 0
    partial_coverage: bool = False
    observed_total: bool = False

    @property
    def average_observed_stream_age_seconds(self) -> float | None:
        """Compatibility alias using the wording from the collection contract."""
        return self.average_stream_age_seconds

    @property
    def language_counts(self) -> tuple[tuple[str, int], ...]:
        """Compatibility alias for callers that call the distribution counts."""
        return self.language_distribution


@dataclass(frozen=True)
class StreamerObservation:
    streamer_id: str
    name: str
    game_id: str
    game_name: str
    viewer_count: int
    language: str
    channel_size_tier: str
    tags: tuple[str, ...] = ()
    stream_id: str | None = None
    login_name: str | None = None
    stream_title: str | None = None
    started_at: str | None = None
    thumbnail_url: str | None = None
    broadcaster_type: str | None = None
    profile_image_url: str | None = None
    category_rank: int | None = None

    @property
    def start_time(self) -> str | None:
        """Human-readable alias for Twitch's ``started_at`` field."""
        return self.started_at


@dataclass(frozen=True)
class Snapshot:
    mode: str
    observed_at: str
    source_name: str
    data: list


class TwitchRateLimitError(RuntimeError):
    """A recoverable Twitch API rate-limit response."""


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _as_tags(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _language_distribution(value: object) -> tuple[tuple[str, int], ...]:
    if isinstance(value, dict):
        pairs = []
        for language, count in value.items():
            parsed_count = max(0, _as_int(count))
            if parsed_count:
                pairs.append((str(language), parsed_count))
        return tuple(sorted(pairs, key=lambda item: (-item[1], item[0])))
    if isinstance(value, (list, tuple)):
        pairs = []
        for item in value:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                parsed_count = max(0, _as_int(item[1]))
                if parsed_count:
                    pairs.append((str(item[0]), parsed_count))
        return tuple(sorted(pairs, key=lambda item: (-item[1], item[0])))
    return ()


def _stream_age_seconds(started_at: object, observed_timestamp: float) -> float | None:
    if not started_at:
        return None
    try:
        parsed = datetime.fromisoformat(str(started_at).strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, observed_timestamp - parsed.timestamp())
    except (TypeError, ValueError, OverflowError):
        return None


def _now_iso() -> str:
    return datetime.fromtimestamp(time.time(), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class TwitchProvider:
    def __init__(
        self,
        snapshot_path: Path,
        client_id: str | None = None,
        client_secret: str | None = None,
        max_stream_pages: int | None = None,
        request_timeout_seconds: float | None = None,
    ):
        self.snapshot_path = snapshot_path
        self.client_id = client_id
        self.client_secret = client_secret
        self.max_stream_pages = max_stream_pages if max_stream_pages is not None else _env_int("TWITCH_MAX_STREAM_PAGES", 3, 1, 10)
        self.max_stream_pages = max(1, min(10, int(self.max_stream_pages)))
        self.request_timeout_seconds = request_timeout_seconds if request_timeout_seconds is not None else _env_float("TWITCH_REQUEST_TIMEOUT_SECONDS", 15.0, 1.0, 120.0)
        self.request_timeout_seconds = max(1.0, min(120.0, float(self.request_timeout_seconds)))
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._rate_limit_remaining: int | None = None
        self._rate_limit_limit: int | None = None
        self._rate_limit_reset: int | None = None

    @property
    def rate_limit_remaining(self) -> int | None:
        return self._rate_limit_remaining

    @property
    def rate_limit_limit(self) -> int | None:
        return self._rate_limit_limit

    @property
    def rate_limit_reset(self) -> int | None:
        return self._rate_limit_reset

    def _demo(self, key: str, factory):
        payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        return Snapshot("Demo", payload["observed_at"], payload.get("source_name", "local demo fixture"), [factory(item) for item in payload.get(key, [])])

    @staticmethod
    def _game_from_item(item: dict) -> GameTrend:
        viewers = max(0, _as_int(item.get("viewer_count")))
        channels = max(0, _as_int(item.get("channel_count")))
        ratio = item.get("viewer_to_channel")
        if ratio is None:
            ratio = viewers / max(channels, 1)
        try:
            ratio = max(0.0, float(ratio))
        except (TypeError, ValueError):
            ratio = 0.0
        return GameTrend(
            str(item["game_id"]),
            str(item["name"]),
            viewers,
            channels,
            _as_float(item.get("growth_score", 0.0) or 0.0),
            _as_tags(item.get("tags", ())),
            rank=_as_int(item.get("rank"), 0) or None,
            viewer_to_channel=ratio,
            top_one_viewer_share=max(0.0, min(1.0, _as_float(item.get("top_one_viewer_share", 0.0) or 0.0))),
            top_five_viewer_share=max(0.0, min(1.0, _as_float(item.get("top_five_viewer_share", 0.0) or 0.0))),
            average_stream_age_seconds=(max(0.0, _as_float(item.get("average_stream_age_seconds"))) if item.get("average_stream_age_seconds") is not None else None),
            language_distribution=_language_distribution(item.get("language_distribution", item.get("language_counts", {}))),
            contributing_stream_rows=max(0, _as_int(item.get("contributing_stream_rows", item.get("channel_count", 0)))),
            pages_collected=max(0, _as_int(item.get("pages_collected", 0))),
            partial_coverage=bool(item.get("partial_coverage", False)),
            observed_total=bool(item.get("observed_total", True)),
        )

    @staticmethod
    def _streamer_from_item(item: dict) -> StreamerObservation:
        streamer_id = str(item.get("streamer_id") or item.get("user_id") or item.get("user_name") or "unknown")
        name = str(item.get("name") or item.get("user_name") or item.get("user_login") or streamer_id)
        return StreamerObservation(
            streamer_id,
            name,
            str(item.get("game_id", "")),
            str(item.get("game_name", "")),
            max(0, _as_int(item.get("viewer_count"))),
            str(item.get("language", "") or ""),
            str(item.get("channel_size_tier", "unknown") or "unknown"),
            _as_tags(item.get("tags", ())),
            stream_id=(str(item["stream_id"]) if item.get("stream_id") else None),
            login_name=(str(item["login_name"]) if item.get("login_name") else None),
            stream_title=(str(item["stream_title"]) if item.get("stream_title") else None),
            started_at=(str(item["started_at"]) if item.get("started_at") else None),
            thumbnail_url=(str(item["thumbnail_url"]) if item.get("thumbnail_url") else None),
            broadcaster_type=(str(item["broadcaster_type"]) if item.get("broadcaster_type") else None),
            profile_image_url=(str(item["profile_image_url"]) if item.get("profile_image_url") else None),
            category_rank=_as_int(item.get("category_rank"), 0) or None,
        )

    def _fallback_game_trends(self) -> Snapshot:
        cached = self._demo("games", self._game_from_item)
        return Snapshot("Fallback", cached.observed_at, f"{cached.source_name} (cached fallback)", cached.data)

    def _fallback_streamers(self, game_id: str) -> Snapshot:
        cached = self._demo("streamers", self._streamer_from_item)
        filtered = [item for item in cached.data if str(item.game_id) == str(game_id)]
        return Snapshot("Fallback", cached.observed_at, f"{cached.source_name} (cached fallback)", filtered)

    def _record_rate_limit_headers(self, headers) -> None:
        if headers is None:
            return

        def header_int(name: str) -> int | None:
            try:
                value = headers.get(name)
                if value is None:
                    value = headers.get(name.lower())
                return int(value) if value is not None else None
            except (AttributeError, TypeError, ValueError):
                return None

        remaining = header_int("Ratelimit-Remaining")
        limit = header_int("Ratelimit-Limit")
        reset = header_int("Ratelimit-Reset")
        if remaining is not None:
            self._rate_limit_remaining = remaining
        if limit is not None:
            self._rate_limit_limit = limit
        if reset is not None:
            self._rate_limit_reset = reset

    def _request_json(self, url: str, params: dict[str, object], retry_auth: bool = True) -> dict:
        query = urllib.parse.urlencode(params, doseq=True)
        request = urllib.request.Request(
            f"{url}?{query}",
            headers={"Client-Id": self.client_id or "", "Authorization": f"Bearer {self._token()}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
                self._record_rate_limit_headers(response.headers)
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            self._record_rate_limit_headers(exc.headers)
            if exc.code == 401 and retry_auth:
                self._access_token = None
                self._token_expires_at = 0.0
                return self._request_json(url, params, retry_auth=False)
            if exc.code == 429:
                raise TwitchRateLimitError("Twitch rate limit reached") from exc
            raise

    def _token(self, force: bool = False) -> str:
        if not force and self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token
        if not self.client_id or not self.client_secret:
            raise RuntimeError("Twitch credentials are not configured")
        body = urllib.parse.urlencode({"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials"}).encode("utf-8")
        request = urllib.request.Request("https://id.twitch.tv/oauth2/token", data=body, method="POST")
        with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self._access_token = payload["access_token"]
        self._token_expires_at = time.time() + int(payload.get("expires_in", 3600))
        return self._access_token

    def _can_make_optional_request(self) -> bool:
        return self._rate_limit_remaining is None or self._rate_limit_remaining > 1

    @staticmethod
    def _stream_key(item: dict, fallback_index: int) -> tuple[str, str]:
        stream_id = str(item.get("id", "") or "").strip()
        user_id = str(item.get("user_id", "") or item.get("user_login", "") or item.get("user_name", "") or "").strip()
        return stream_id or f"user:{user_id or fallback_index}", user_id

    def _collect_stream_pages(self, game_id: str | None = None) -> tuple[list[dict], int, bool]:
        streams: list[dict] = []
        seen_streams: set[str] = set()
        cursor: str | None = None
        pages_collected = 0
        partial_coverage = False

        while pages_collected < self.max_stream_pages:
            if cursor and not self._can_make_optional_request():
                partial_coverage = True
                break
            params: dict[str, object] = {"first": "100"}
            if game_id is not None:
                params["game_id"] = str(game_id)
            if cursor:
                params["after"] = cursor
            payload = self._request_json("https://api.twitch.tv/helix/streams", params)
            pages_collected += 1
            page_data = payload.get("data", [])
            if not isinstance(page_data, list):
                raise ValueError("Twitch streams response data must be an array")
            if not page_data:
                break
            for index, item in enumerate(page_data):
                if not isinstance(item, dict):
                    continue
                stream_key, _user_id = self._stream_key(item, index)
                if stream_key in seen_streams:
                    continue
                seen_streams.add(stream_key)
                streams.append(item)
            pagination = payload.get("pagination") or {}
            next_cursor = pagination.get("cursor") if isinstance(pagination, dict) else None
            if not next_cursor:
                break
            cursor = str(next_cursor)
            if pages_collected >= self.max_stream_pages:
                partial_coverage = True
                break
        return streams, pages_collected, partial_coverage

    @staticmethod
    def _metric_for_streams(streams: list[dict], observed_timestamp: float) -> dict[str, object]:
        viewers: list[int] = []
        channels: set[str] = set()
        ages: list[float] = []
        languages: Counter[str] = Counter()
        name = ""
        for index, item in enumerate(streams):
            viewer_count = max(0, _as_int(item.get("viewer_count")))
            viewers.append(viewer_count)
            _stream_key, user_id = TwitchProvider._stream_key(item, index)
            channels.add(user_id or _stream_key)
            name = name or str(item.get("game_name", "") or "")
            age = _stream_age_seconds(item.get("started_at"), observed_timestamp)
            if age is not None:
                ages.append(age)
            language = str(item.get("language", "") or "").strip().casefold()
            if language:
                languages[language] += 1
        total_viewers = sum(viewers)
        top_one = max(viewers, default=0) / total_viewers if total_viewers else 0.0
        top_five = sum(sorted(viewers, reverse=True)[:5]) / total_viewers if total_viewers else 0.0
        return {
            "name": name,
            "viewers": total_viewers,
            "channels": channels,
            "viewer_counts": viewers,
            "ages": ages,
            "languages": languages,
            "top_one": top_one,
            "top_five": top_five,
        }

    def get_game_trends(self) -> Snapshot:
        if not self.client_id or not self.client_secret:
            return self._demo("games", self._game_from_item)
        try:
            top_payload = self._request_json("https://api.twitch.tv/helix/games/top", {"first": "100"})
            top_data = top_payload.get("data", [])
            if not isinstance(top_data, list):
                raise ValueError("Twitch top games response data must be an array")
            if self._can_make_optional_request():
                stream_rows, pages_collected, partial_coverage = self._collect_stream_pages()
            else:
                stream_rows, pages_collected, partial_coverage = [], 0, True
            observed_timestamp = time.time()
            by_game: dict[str, list[dict]] = {}
            for item in stream_rows:
                game_id = str(item.get("game_id", "") or "").strip()
                if game_id:
                    by_game.setdefault(game_id, []).append(item)

            games: list[GameTrend] = []
            seen_ids: set[str] = set()
            for index, item in enumerate(top_data, start=1):
                if not isinstance(item, dict) or not item.get("id") or not item.get("name"):
                    continue
                game_id = str(item["id"])
                metric = self._metric_for_streams(by_game.get(game_id, []), observed_timestamp)
                channels = metric["channels"]
                viewers = int(metric["viewers"])
                ages = metric["ages"]
                languages = metric["languages"]
                games.append(GameTrend(
                    game_id,
                    str(item["name"]),
                    viewers,
                    len(channels),
                    0.0,
                    (),
                    rank=index,
                    viewer_to_channel=viewers / max(len(channels), 1),
                    top_one_viewer_share=float(metric["top_one"]),
                    top_five_viewer_share=float(metric["top_five"]),
                    average_stream_age_seconds=(sum(ages) / len(ages) if ages else None),
                    language_distribution=tuple(sorted(languages.items(), key=lambda entry: (-entry[1], entry[0]))),
                    contributing_stream_rows=len(by_game.get(game_id, [])),
                    pages_collected=pages_collected,
                    partial_coverage=partial_coverage,
                    observed_total=bool(by_game.get(game_id)),
                ))
                seen_ids.add(game_id)
            for game_id, rows in by_game.items():
                if game_id in seen_ids:
                    continue
                metric = self._metric_for_streams(rows, observed_timestamp)
                channels = metric["channels"]
                viewers = int(metric["viewers"])
                ages = metric["ages"]
                languages = metric["languages"]
                games.append(GameTrend(
                    game_id,
                    str(metric["name"]),
                    viewers,
                    len(channels),
                    0.0,
                    (),
                    viewer_to_channel=viewers / max(len(channels), 1),
                    top_one_viewer_share=float(metric["top_one"]),
                    top_five_viewer_share=float(metric["top_five"]),
                    average_stream_age_seconds=(sum(ages) / len(ages) if ages else None),
                    language_distribution=tuple(sorted(languages.items(), key=lambda entry: (-entry[1], entry[0]))),
                    contributing_stream_rows=len(rows),
                    pages_collected=pages_collected,
                    partial_coverage=partial_coverage,
                    observed_total=True,
                ))
            return Snapshot("Live", _now_iso(), f"Twitch Helix /games/top + /streams (bounded first 100, up to {self.max_stream_pages} pages; observed totals)", games)
        except (OSError, ValueError, KeyError, RuntimeError, HTTPError):
            return self._fallback_game_trends()

    def _enrich_streamers(self, observations: list[StreamerObservation]) -> list[StreamerObservation]:
        if not observations or not self._can_make_optional_request():
            return observations
        ids = [item.streamer_id for item in observations if item.streamer_id]
        if not ids:
            return observations
        payload = self._request_json("https://api.twitch.tv/helix/users", {"id": ids[:100]})
        users = payload.get("data", [])
        if not isinstance(users, list):
            return observations
        profiles = {str(item.get("id")): item for item in users if isinstance(item, dict) and item.get("id")}
        enriched = []
        for observation in observations:
            profile = profiles.get(observation.streamer_id, {})
            enriched.append(replace(
                observation,
                name=str(profile.get("display_name") or observation.name),
                login_name=observation.login_name or (str(profile["login"]) if profile.get("login") else None),
                broadcaster_type=observation.broadcaster_type or (str(profile["broadcaster_type"]) if profile.get("broadcaster_type") else None),
                profile_image_url=observation.profile_image_url or (str(profile["profile_image_url"]) if profile.get("profile_image_url") else None),
            ))
        return enriched

    def get_streamers(self, game_id: str) -> Snapshot:
        if not self.client_id or not self.client_secret:
            cached = self._fallback_streamers(game_id)
            return Snapshot("Demo", cached.observed_at, "local demo fixture", cached.data)
        try:
            stream_rows, _pages_collected, _partial_coverage = self._collect_stream_pages(str(game_id))
            observed = []
            for item in stream_rows:
                if not isinstance(item, dict):
                    continue
                _stream_key, user_id = self._stream_key(item, len(observed))
                streamer_id = user_id or str(item.get("user_name", "") or item.get("user_login", "") or "").strip()
                if not streamer_id:
                    continue
                observed.append(StreamerObservation(
                    streamer_id=streamer_id,
                    name=str(item.get("user_name") or item.get("user_login") or streamer_id),
                    game_id=str(item.get("game_id", game_id) or game_id),
                    game_name=str(item.get("game_name", "") or ""),
                    viewer_count=max(0, _as_int(item.get("viewer_count"))),
                    language=str(item.get("language", "") or ""),
                    channel_size_tier=str(item.get("channel_size_tier", "unknown") or "unknown"),
                    tags=_as_tags(item.get("tags", ())),
                    stream_id=(str(item["id"]) if item.get("id") else None),
                    login_name=(str(item["user_login"]) if item.get("user_login") else None),
                    stream_title=(str(item["title"]) if item.get("title") else None),
                    started_at=(str(item["started_at"]) if item.get("started_at") else None),
                    thumbnail_url=(str(item["thumbnail_url"]) if item.get("thumbnail_url") else None),
                    broadcaster_type=(str(item["broadcaster_type"]) if item.get("broadcaster_type") else None),
                    profile_image_url=(str(item["profile_image_url"]) if item.get("profile_image_url") else None),
                ))
            observed.sort(key=lambda item: (-item.viewer_count, item.streamer_id))
            observed = [replace(item, category_rank=index) for index, item in enumerate(observed, start=1)]
            try:
                observed = self._enrich_streamers(observed)
            except (OSError, ValueError, KeyError, RuntimeError, HTTPError):
                pass
            return Snapshot("Live", _now_iso(), f"Twitch Helix /streams (bounded first 100, up to {self.max_stream_pages} pages; observed totals)", observed)
        except (OSError, ValueError, KeyError, RuntimeError, HTTPError):
            return self._fallback_streamers(game_id)

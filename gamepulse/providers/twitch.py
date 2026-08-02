"""Twitch Helix provider with a clearly labelled offline demo fallback."""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GameTrend:
    game_id: str
    name: str
    viewer_count: int
    channel_count: int
    growth_score: float = 0.0
    tags: tuple[str, ...] = ()


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


@dataclass(frozen=True)
class Snapshot:
    mode: str
    observed_at: str
    source_name: str
    data: list


class TwitchProvider:
    def __init__(self, snapshot_path: Path, client_id: str | None = None, client_secret: str | None = None):
        self.snapshot_path = snapshot_path
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    def _demo(self, key: str, factory):
        payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        return Snapshot("Demo", payload["observed_at"], payload.get("source_name", "local demo fixture"), [factory(item) for item in payload.get(key, [])])

    def _fallback_game_trends(self) -> Snapshot:
        cached = self._demo("games", lambda item: GameTrend(
            str(item["game_id"]),
            item["name"],
            int(item.get("viewer_count", 0)),
            int(item.get("channel_count", 0)),
            float(item.get("growth_score", 0)),
            tuple(item.get("tags", [])),
        ))
        return Snapshot("Fallback", cached.observed_at, f"{cached.source_name} (cached fallback)", cached.data)

    def _fallback_streamers(self, game_id: str) -> Snapshot:
        cached = self._demo("streamers", lambda item: StreamerObservation(
            str(item["streamer_id"]),
            item["name"],
            str(item["game_id"]),
            item["game_name"],
            int(item.get("viewer_count", 0)),
            item.get("language", ""),
            item.get("channel_size_tier", "unknown"),
            tuple(item.get("tags", [])),
        ))
        filtered = [item for item in cached.data if str(item.game_id) == str(game_id)]
        return Snapshot("Fallback", cached.observed_at, f"{cached.source_name} (cached fallback)", filtered)

    def _request_json(self, url: str, params: dict[str, str]) -> dict:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(f"{url}?{query}", headers={"Client-Id": self.client_id or "", "Authorization": f"Bearer {self._token()}"})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def _token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token
        if not self.client_id or not self.client_secret:
            raise RuntimeError("Twitch credentials are not configured")
        body = urllib.parse.urlencode({"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials"}).encode("utf-8")
        request = urllib.request.Request("https://id.twitch.tv/oauth2/token", data=body, method="POST")
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self._access_token = payload["access_token"]
        self._token_expires_at = time.time() + int(payload.get("expires_in", 3600))
        return self._access_token

    def get_game_trends(self) -> Snapshot:
        if not self.client_id or not self.client_secret:
            return self._demo("games", lambda item: GameTrend(str(item["game_id"]), item["name"], int(item.get("viewer_count", 0)), int(item.get("channel_count", 0)), float(item.get("growth_score", 0)), tuple(item.get("tags", []))))
        try:
            top_payload = self._request_json("https://api.twitch.tv/helix/games/top", {"first": "100"})
            streams_payload = self._request_json("https://api.twitch.tv/helix/streams", {"first": "100"})
            metrics: dict[str, dict[str, object]] = {}
            for item in streams_payload.get("data", []):
                game_id = str(item.get("game_id", ""))
                if not game_id:
                    continue
                metric = metrics.setdefault(game_id, {"name": item.get("game_name", ""), "viewers": 0, "channels": set()})
                metric["viewers"] = int(metric["viewers"]) + max(0, int(item.get("viewer_count", 0)))
                metric["channels"].add(str(item.get("user_id", item.get("user_name", ""))))
            games = []
            seen_ids = set()
            for item in top_payload.get("data", []):
                game_id = str(item["id"])
                metric = metrics.get(game_id, {"name": item["name"], "viewers": 0, "channels": set()})
                games.append(GameTrend(game_id, item["name"], int(metric["viewers"]), len(metric["channels"]), 0.0))
                seen_ids.add(game_id)
            for game_id, metric in metrics.items():
                if game_id not in seen_ids:
                    games.append(GameTrend(game_id, str(metric["name"]), int(metric["viewers"]), len(metric["channels"]), 0.0))
            return Snapshot("Live", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "Twitch Helix /games/top + /streams (bounded first 100)", games)
        except (OSError, ValueError, KeyError, RuntimeError):
            return self._fallback_game_trends()

    def get_streamers(self, game_id: str) -> Snapshot:
        if not self.client_id or not self.client_secret:
            cached = self._fallback_streamers(game_id)
            return Snapshot("Demo", cached.observed_at, "local demo fixture", cached.data)
        try:
            payload = self._request_json("https://api.twitch.tv/helix/streams", {"game_id": str(game_id), "first": "100"})
            streamers = [StreamerObservation(str(item["user_id"]), item["user_name"], str(item.get("game_id", game_id)), item.get("game_name", ""), int(item.get("viewer_count", 0)), item.get("language", ""), "unknown", tuple(item.get("tags", []))) for item in payload.get("data", [])]
            return Snapshot("Live", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "Twitch Helix /streams (bounded first 100)", streamers)
        except (OSError, ValueError, KeyError, RuntimeError):
            return self._fallback_streamers(game_id)

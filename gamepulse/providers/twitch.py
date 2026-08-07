"""Optional Twitch Helix provider implementing GamePulse's neutral contracts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

from gamepulse.providers.contracts import CreatorSignal, GameSignal, SignalSnapshot
from gamepulse.providers.snapshot import load_snapshot


# Compatibility shims retained for older tests/callers. New code should use
# GameSignal and CreatorSignal from gamepulse.providers.contracts.
@dataclass(frozen=True)
class GameTrend:
    game_id: str
    name: str
    viewer_count: int
    channel_count: int
    growth_score: float = 0.0
    tags: tuple[str, ...] = ()

    def to_signal(self, *, observed_at: str = "", source_name: str = "Twitch", mode: str = "Imported") -> GameSignal:
        return GameSignal(
            game_id=self.game_id,
            name=self.name,
            audience_value=float(self.viewer_count),
            audience_metric="twitch_viewers",
            competition_value=float(self.channel_count),
            competition_metric="twitch_live_channels",
            growth_score=float(self.growth_score),
            tags=tuple(self.tags),
            platform="Twitch",
            source_name=source_name,
            observed_at=observed_at,
            confidence="live" if mode.casefold() == "live" else "imported",
            source_mode=mode,
        )


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

    def to_signal(self, *, observed_at: str = "", source_name: str = "Twitch", mode: str = "Imported") -> CreatorSignal:
        return CreatorSignal(
            creator_id=self.streamer_id,
            name=self.name,
            platform="Twitch",
            profile_url=None,
            game_id=self.game_id,
            game_name=self.game_name,
            audience_value=float(self.viewer_count),
            audience_metric="twitch_viewers",
            language=self.language,
            channel_size_tier=self.channel_size_tier,
            tags=tuple(self.tags),
            games=(self.game_name,) if self.game_name else (),
            observed_at=observed_at,
            source_name=source_name,
            confidence="live" if mode.casefold() == "live" else "imported",
            source_mode=mode,
        )


Snapshot = SignalSnapshot


class TwitchProvider:
    """Twitch enhancement provider; credentials are always optional."""

    def __init__(self, snapshot_path: Path, client_id: str | None = None, client_secret: str | None = None):
        self.snapshot_path = Path(snapshot_path)
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    @property
    def available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _demo_bundle(self):
        return load_snapshot(self.snapshot_path)

    def _fallback_games(self, reason: str = "cached fallback") -> SignalSnapshot[GameSignal]:
        bundle = self._demo_bundle()
        source = f"{bundle.games.source_name} ({reason})"
        data = [
            GameSignal(**{**item.__dict__, "source_name": source, "source_mode": "Fallback"})
            for item in bundle.games.data
        ]
        return SignalSnapshot("Fallback", bundle.games.observed_at, source, data, "fallback")

    def _fallback_creators(self, game_id: str | None = None, reason: str = "cached fallback") -> SignalSnapshot[CreatorSignal]:
        bundle = self._demo_bundle()
        data = [item for item in bundle.creators.data if game_id is None or str(item.game_id) == str(game_id)]
        source = f"{bundle.creators.source_name} ({reason})"
        data = [
            CreatorSignal(**{**item.__dict__, "source_name": source, "source_mode": "Fallback"})
            for item in data
        ]
        return SignalSnapshot("Fallback", bundle.creators.observed_at, source, data, "fallback")

    def _request_json(self, url: str, params: dict[str, str]) -> dict:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"{url}?{query}",
            headers={"Client-Id": self.client_id or "", "Authorization": f"Bearer {self._token()}"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def _token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token
        if not self.available:
            raise RuntimeError("Twitch credentials are not configured")
        body = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            }
        ).encode("utf-8")
        request = urllib.request.Request("https://id.twitch.tv/oauth2/token", data=body, method="POST")
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self._access_token = str(payload["access_token"])
        self._token_expires_at = time.time() + int(payload.get("expires_in", 3600))
        return self._access_token

    def get_game_trends(self) -> SignalSnapshot[GameSignal]:
        if not self.available:
            bundle = self._demo_bundle()
            return bundle.games
        try:
            top_payload = self._request_json("https://api.twitch.tv/helix/games/top", {"first": "100"})
            streams_payload = self._request_json("https://api.twitch.tv/helix/streams", {"first": "100"})
            metrics: dict[str, dict[str, object]] = {}
            for item in streams_payload.get("data", []):
                game_id = str(item.get("game_id", ""))
                if not game_id:
                    continue
                metric = metrics.setdefault(
                    game_id,
                    {"name": item.get("game_name", ""), "viewers": 0, "channels": set(), "tags": set()},
                )
                metric["viewers"] = int(metric["viewers"]) + max(0, int(item.get("viewer_count", 0)))
                metric["channels"].add(str(item.get("user_id", item.get("user_name", ""))))
                metric["tags"].update(str(tag) for tag in item.get("tags", []) if str(tag).strip())

            observed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            source_name = "Twitch Helix /games/top + /streams (bounded first 100)"
            games: list[GameSignal] = []
            seen_ids: set[str] = set()
            for item in top_payload.get("data", []):
                game_id = str(item["id"])
                metric = metrics.get(game_id, {"name": item["name"], "viewers": 0, "channels": set(), "tags": set()})
                games.append(
                    GameSignal(
                        game_id=game_id,
                        name=str(item["name"]),
                        audience_value=float(metric["viewers"]),
                        audience_metric="twitch_viewers",
                        competition_value=float(len(metric["channels"])),
                        competition_metric="twitch_live_channels",
                        growth_score=None,
                        tags=tuple(sorted(metric["tags"])),
                        platform="Twitch",
                        source_name=source_name,
                        observed_at=observed_at,
                        confidence="live-bounded",
                        source_mode="Live",
                    )
                )
                seen_ids.add(game_id)
            for game_id, metric in metrics.items():
                if game_id in seen_ids:
                    continue
                games.append(
                    GameSignal(
                        game_id=game_id,
                        name=str(metric["name"]),
                        audience_value=float(metric["viewers"]),
                        audience_metric="twitch_viewers",
                        competition_value=float(len(metric["channels"])),
                        competition_metric="twitch_live_channels",
                        growth_score=None,
                        tags=tuple(sorted(metric["tags"])),
                        platform="Twitch",
                        source_name=source_name,
                        observed_at=observed_at,
                        confidence="live-bounded",
                        source_mode="Live",
                    )
                )
            return SignalSnapshot("Live", observed_at, source_name, games, "live-bounded")
        except (OSError, ValueError, KeyError, RuntimeError, TypeError):
            return self._fallback_games("cached fallback; live request unavailable")

    def get_creators(
        self,
        game_id: str | None = None,
        game_name: str | None = None,
    ) -> SignalSnapshot[CreatorSignal]:
        if not self.available:
            bundle = self._demo_bundle()
            data = [
                item
                for item in bundle.creators.data
                if (game_id is None or str(item.game_id) == str(game_id))
                and (not game_name or not item.game_name or item.game_name.casefold() == game_name.casefold())
            ]
            return SignalSnapshot(bundle.creators.mode, bundle.creators.observed_at, bundle.creators.source_name, data, bundle.creators.confidence)
        try:
            params = {"first": "100"}
            if game_id is not None:
                params["game_id"] = str(game_id)
            payload = self._request_json("https://api.twitch.tv/helix/streams", params)
            observed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            source_name = "Twitch Helix /streams (bounded first 100)"
            creators = [
                CreatorSignal(
                    creator_id=str(item["user_id"]),
                    name=str(item.get("user_name") or item.get("user_login") or item["user_id"]),
                    platform="Twitch",
                    profile_url=(f"https://twitch.tv/{item['user_login']}" if item.get("user_login") else None),
                    game_id=(str(item.get("game_id")) if item.get("game_id") else None),
                    game_name=(str(item.get("game_name")) if item.get("game_name") else None),
                    audience_value=float(max(0, int(item.get("viewer_count", 0)))),
                    audience_metric="twitch_viewers",
                    language=str(item.get("language") or ""),
                    channel_size_tier="unknown",
                    tags=tuple(str(tag) for tag in item.get("tags", []) if str(tag).strip()),
                    games=((str(item.get("game_name")),) if item.get("game_name") else ()),
                    observed_at=observed_at,
                    source_name=source_name,
                    confidence="live-bounded",
                    source_mode="Live",
                )
                for item in payload.get("data", [])
            ]
            return SignalSnapshot("Live", observed_at, source_name, creators, "live-bounded")
        except (OSError, ValueError, KeyError, RuntimeError, TypeError):
            return self._fallback_creators(game_id, "cached fallback; live request unavailable")

    def get_streamers(self, game_id: str) -> SignalSnapshot[CreatorSignal]:
        """Backward-compatible alias for the normalized creator provider method."""

        return self.get_creators(game_id=str(game_id))

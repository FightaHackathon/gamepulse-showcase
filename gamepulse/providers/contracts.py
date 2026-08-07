"""Source-neutral signal contracts shared by GamePulse providers and UIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Protocol, TypeVar


@dataclass(frozen=True)
class GameSignal:
    """Normalized game-level evidence from any legitimate data source.

    ``audience_value`` and ``competition_value`` are deliberately paired with
    metric identifiers. A Steam player count is therefore never implicitly
    treated as a Twitch viewer count, and unavailable competition remains
    ``None`` instead of a fabricated zero.
    """

    game_id: str
    name: str
    audience_value: float | None
    audience_metric: str | None
    competition_value: float | None
    competition_metric: str | None
    growth_score: float | None
    tags: tuple[str, ...]
    platform: str
    source_name: str
    observed_at: str
    confidence: str = "unknown"
    source_mode: str = "Unknown"
    sentiment_score: float | None = None
    promotion_score: float | None = None
    freshness_score: float | None = None
    genres: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    @property
    def viewer_count(self) -> int | None:
        """Compatibility access for genuine Twitch viewer observations only."""

        if self.audience_metric != "twitch_viewers" or self.audience_value is None:
            return None
        return max(0, int(self.audience_value))

    @property
    def channel_count(self) -> int | None:
        """Compatibility access for genuine Twitch channel observations only."""

        if self.competition_metric != "twitch_live_channels" or self.competition_value is None:
            return None
        return max(0, int(self.competition_value))


@dataclass(frozen=True)
class CreatorSignal:
    """Normalized creator profile/observation with explicit provenance."""

    creator_id: str
    name: str
    platform: str
    profile_url: str | None
    game_id: str | None
    game_name: str | None
    audience_value: float | None
    audience_metric: str | None
    language: str
    channel_size_tier: str
    tags: tuple[str, ...]
    observed_at: str
    source_name: str
    confidence: str = "unknown"
    source_mode: str = "Manual"
    games: tuple[str, ...] = ()

    @property
    def streamer_id(self) -> str:
        """Compatibility alias for older creator-fit callers."""

        return self.creator_id

    @property
    def viewer_count(self) -> int | None:
        if self.audience_metric not in {"avg_viewers", "twitch_viewers"} or self.audience_value is None:
            return None
        return max(0, int(self.audience_value))


T = TypeVar("T")


@dataclass(frozen=True)
class SignalSnapshot(Generic[T]):
    mode: str
    observed_at: str
    source_name: str
    data: list[T] = field(default_factory=list)
    confidence: str = "unknown"

    @property
    def source_mode(self) -> str:
        return self.mode


class GameSignalProvider(Protocol):
    def get_game_trends(self) -> SignalSnapshot[GameSignal]:
        """Return normalized game-level signals."""


class CreatorSignalProvider(Protocol):
    def get_creators(
        self,
        game_id: str | None = None,
        game_name: str | None = None,
    ) -> SignalSnapshot[CreatorSignal]:
        """Return normalized creator records, optionally filtered by game."""


# Short compatibility name used by older modules while they migrate.
Snapshot = SignalSnapshot

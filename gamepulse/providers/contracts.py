from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class GameIdentity:
    steam_app_id: int
    name: str
    twitch_id: str | None = None
    release_date: str | None = None

    @property
    def twitch_lookup(self) -> str:
        return self.twitch_id or self.name


@dataclass(frozen=True)
class ProviderMetric:
    metric: str
    value: float | int | str | None
    observed_at: datetime
    source_name: str
    source_mode: str
    confidence: str
    source_url: str | None = None

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        for field_name in ("metric", "source_name", "source_mode", "confidence"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")


class ProviderError(RuntimeError):
    """Recoverable external provider error."""


class GameSignalProvider(Protocol):
    provider_name: str

    def fetch(self, game: GameIdentity) -> list[ProviderMetric]: ...

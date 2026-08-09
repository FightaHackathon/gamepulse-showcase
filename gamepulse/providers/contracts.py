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


@dataclass(frozen=True)
class ReviewExcerpt:
    review_id: str
    text: str
    recommended: bool
    helpful_votes: int | None
    funny_votes: int | None
    created_at_unix: int | None
    source_name: str
    source_mode: str
    source_url: str | None = None

    def __post_init__(self) -> None:
        if not str(self.review_id).strip():
            raise ValueError("review_id is required")
        if not str(self.text).strip():
            raise ValueError("text is required")
        if not str(self.source_name).strip() or not str(self.source_mode).strip():
            raise ValueError("review provenance is required")


class ProviderError(RuntimeError):
    """Recoverable external provider error."""


class GameSignalProvider(Protocol):
    provider_name: str
    signal_type: str

    def fetch(self, game: GameIdentity) -> list[ProviderMetric]: ...

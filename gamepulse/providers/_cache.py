"""Small provider-local JSON cache for bounded public endpoint responses."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from collections.abc import Callable


@dataclass(frozen=True)
class CacheHit:
    payload: object
    fresh: bool
    age_seconds: float
    stored_at: float


class JsonResponseCache:
    """Read/write one keyed JSON cache file without making catalogue requests."""

    def __init__(
        self,
        path: Path | str | None,
        *,
        ttl_seconds: float = 24 * 60 * 60,
        clock: Callable[[], float] = time.time,
    ):
        self.path = Path(path) if path else None
        self.ttl_seconds = max(0.0, float(ttl_seconds))
        self.clock = clock

    def get(self, key: str) -> CacheHit | None:
        if self.path is None or not self.path.is_file():
            return None
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            entry = document.get("entries", {}).get(key)
            stored_at = float(entry["stored_at"])
            payload = entry["payload"]
        except (OSError, TypeError, ValueError, KeyError, AttributeError):
            return None
        age_seconds = max(0.0, float(self.clock()) - stored_at)
        return CacheHit(payload, age_seconds <= self.ttl_seconds, age_seconds, stored_at)

    def put(self, key: str, payload: object) -> None:
        if self.path is None:
            return
        document: dict[str, object] = {"version": 1, "entries": {}}
        try:
            existing = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else document
            if isinstance(existing, dict) and isinstance(existing.get("entries"), dict):
                document["entries"] = existing["entries"]
        except (OSError, TypeError, ValueError):
            pass
        entries = document["entries"]
        assert isinstance(entries, dict)
        entries[key] = {"stored_at": float(self.clock()), "payload": payload}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        except (OSError, TypeError, ValueError):
            # A cache is an optimization; a read-only or unavailable path must
            # never turn a successful provider response into an error.
            return

"""Manual/opt-in creator directory provider for Developer Mode."""

from __future__ import annotations

import csv
from pathlib import Path
import re

from gamepulse.providers.contracts import CreatorSignal, SignalSnapshot


class CreatorDirectoryError(ValueError):
    """Raised when a creator directory cannot be parsed safely."""


def _split_values(value: object) -> tuple[str, ...]:
    return tuple(part.strip() for part in str(value or "").split("|") if part.strip())


def _normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _optional_float(value: object, *, row_number: int) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise CreatorDirectoryError(f"creator row {row_number}: avg_viewers must be numeric or blank") from exc
    if number < 0:
        raise CreatorDirectoryError(f"creator row {row_number}: avg_viewers cannot be negative")
    return number


def _source_mode(source: str) -> str:
    normalized = source.casefold().replace("-", "_").replace(" ", "_")
    if normalized in {"creator_submitted", "opt_in", "optin"}:
        return "Creator submitted"
    if normalized in {"demo", "example", "competition_demo"}:
        return "Demo"
    if normalized in {"snapshot", "imported", "authorized_export"}:
        return "Imported"
    return "Manual"


class CreatorDirectoryProvider:
    """Load date-stamped creator profiles without requiring a platform API."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def _load(self) -> list[CreatorSignal]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise CreatorDirectoryError("creator directory requires a header row")
            required = {"creator_id", "name", "platform", "observed_at", "source", "confidence"}
            missing = required - {str(name).strip() for name in reader.fieldnames}
            if missing:
                raise CreatorDirectoryError(f"creator directory missing columns: {', '.join(sorted(missing))}")
            creators: list[CreatorSignal] = []
            for row_number, row in enumerate(reader, start=2):
                creator_id = str(row.get("creator_id") or "").strip()
                name = str(row.get("name") or "").strip()
                platform = str(row.get("platform") or "").strip()
                observed_at = str(row.get("observed_at") or "").strip()
                source = str(row.get("source") or "").strip()
                confidence = str(row.get("confidence") or "").strip()
                if not all((creator_id, name, platform, observed_at, source, confidence)):
                    raise CreatorDirectoryError(
                        f"creator row {row_number}: creator_id, name, platform, observed_at, source, and confidence are required"
                    )
                audience = _optional_float(row.get("avg_viewers"), row_number=row_number)
                games = _split_values(row.get("games"))
                game_name = str(row.get("game_name") or "").strip() or (games[0] if len(games) == 1 else None)
                creators.append(
                    CreatorSignal(
                        creator_id=creator_id,
                        name=name,
                        platform=platform,
                        profile_url=str(row.get("profile_url") or "").strip() or None,
                        game_id=str(row.get("game_id") or "").strip() or None,
                        game_name=game_name,
                        audience_value=audience,
                        audience_metric="avg_viewers" if audience is not None else None,
                        language=str(row.get("language") or "").strip(),
                        channel_size_tier=str(row.get("channel_size_tier") or "unknown").strip() or "unknown",
                        tags=_split_values(row.get("tags")),
                        games=games,
                        observed_at=observed_at,
                        source_name=source,
                        confidence=confidence,
                        source_mode=_source_mode(source),
                    )
                )
        return creators

    def get_creators(
        self,
        game_id: str | None = None,
        game_name: str | None = None,
    ) -> SignalSnapshot[CreatorSignal]:
        creators = self._load()
        if game_id is not None:
            creators = [creator for creator in creators if creator.game_id in {None, str(game_id)}]
        if game_name:
            target = _normalize(game_name)
            creators = [
                creator
                for creator in creators
                if not creator.games
                or target in {_normalize(value) for value in creator.games}
                or _normalize(creator.game_name) == target
            ]
        observed_at = max((creator.observed_at for creator in creators if creator.observed_at), default="")
        modes = {creator.source_mode for creator in creators}
        mode = next(iter(modes)) if len(modes) == 1 else "Mixed" if modes else "Unavailable"
        confidence = "mixed" if len(modes) > 1 else "directory"
        return SignalSnapshot(mode, observed_at, f"Creator directory: {self.path.name}", creators, confidence)

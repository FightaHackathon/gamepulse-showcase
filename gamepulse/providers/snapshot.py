"""Versioned imported-snapshot support for source-neutral GamePulse signals."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from gamepulse.providers.contracts import CreatorSignal, GameSignal, SignalSnapshot


SCHEMA_VERSION = 2


@dataclass(frozen=True)
class ImportedSignals:
    schema_version: int
    games: SignalSnapshot[GameSignal]
    creators: SignalSnapshot[CreatorSignal]


def _optional_number(value: object, field: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric or null") from exc


def _tuple_values(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split("|") if part.strip())
    if isinstance(value, (list, tuple)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    raise ValueError("multi-value fields must be an array, pipe-delimited string, or null")


def _required_text(item: dict[str, Any], field: str) -> str:
    value = str(item.get(field, "")).strip()
    if not value:
        raise ValueError(f"snapshot item requires {field}")
    return value


def _game_v2(item: dict[str, Any], *, observed_at: str, source_name: str, source_mode: str, confidence: str) -> GameSignal:
    return GameSignal(
        game_id=_required_text(item, "game_id"),
        name=_required_text(item, "name"),
        audience_value=_optional_number(item.get("audience_value"), "audience_value"),
        audience_metric=(str(item["audience_metric"]).strip() if item.get("audience_metric") else None),
        competition_value=_optional_number(item.get("competition_value"), "competition_value"),
        competition_metric=(str(item["competition_metric"]).strip() if item.get("competition_metric") else None),
        growth_score=_optional_number(item.get("growth_score"), "growth_score"),
        tags=_tuple_values(item.get("tags")),
        genres=_tuple_values(item.get("genres")),
        platform=_required_text(item, "platform"),
        source_name=str(item.get("source_name") or source_name),
        observed_at=str(item.get("observed_at") or observed_at),
        confidence=str(item.get("confidence") or confidence),
        source_mode=str(item.get("source_mode") or source_mode),
        sentiment_score=_optional_number(item.get("sentiment_score"), "sentiment_score"),
        promotion_score=_optional_number(item.get("promotion_score"), "promotion_score"),
        freshness_score=_optional_number(item.get("freshness_score"), "freshness_score"),
    )


def _creator_v2(item: dict[str, Any], *, observed_at: str, source_name: str, source_mode: str, confidence: str) -> CreatorSignal:
    creator_id = str(item.get("creator_id") or item.get("streamer_id") or "").strip()
    if not creator_id:
        raise ValueError("snapshot creator requires creator_id")
    return CreatorSignal(
        creator_id=creator_id,
        name=_required_text(item, "name"),
        platform=_required_text(item, "platform"),
        profile_url=(str(item["profile_url"]).strip() if item.get("profile_url") else None),
        game_id=(str(item["game_id"]).strip() if item.get("game_id") else None),
        game_name=(str(item["game_name"]).strip() if item.get("game_name") else None),
        audience_value=_optional_number(item.get("audience_value"), "audience_value"),
        audience_metric=(str(item["audience_metric"]).strip() if item.get("audience_metric") else None),
        language=str(item.get("language") or "").strip(),
        channel_size_tier=str(item.get("channel_size_tier") or "unknown").strip(),
        tags=_tuple_values(item.get("tags")),
        games=_tuple_values(item.get("games")),
        observed_at=str(item.get("observed_at") or observed_at),
        source_name=str(item.get("source_name") or item.get("source") or source_name),
        confidence=str(item.get("confidence") or confidence),
        source_mode=str(item.get("source_mode") or source_mode),
    )


def _legacy_game(item: dict[str, Any], *, observed_at: str, source_name: str, source_mode: str) -> GameSignal:
    viewers = _optional_number(item.get("viewer_count"), "viewer_count")
    channels = _optional_number(item.get("channel_count"), "channel_count")
    return GameSignal(
        game_id=_required_text(item, "game_id"),
        name=_required_text(item, "name"),
        audience_value=viewers,
        audience_metric="twitch_viewers" if viewers is not None else None,
        competition_value=channels,
        competition_metric="twitch_live_channels" if channels is not None else None,
        growth_score=_optional_number(item.get("growth_score"), "growth_score"),
        tags=_tuple_values(item.get("tags")),
        platform="Twitch",
        source_name=source_name,
        observed_at=observed_at,
        confidence="demo" if source_mode.casefold() == "demo" else "imported",
        source_mode=source_mode,
    )


def _legacy_creator(item: dict[str, Any], *, observed_at: str, source_name: str, source_mode: str) -> CreatorSignal:
    viewers = _optional_number(item.get("viewer_count"), "viewer_count")
    return CreatorSignal(
        creator_id=str(item.get("streamer_id") or item.get("creator_id") or "").strip(),
        name=_required_text(item, "name"),
        platform="Twitch",
        profile_url=None,
        game_id=(str(item["game_id"]) if item.get("game_id") is not None else None),
        game_name=(str(item["game_name"]) if item.get("game_name") else None),
        audience_value=viewers,
        audience_metric="twitch_viewers" if viewers is not None else None,
        language=str(item.get("language") or ""),
        channel_size_tier=str(item.get("channel_size_tier") or "unknown"),
        tags=_tuple_values(item.get("tags")),
        observed_at=observed_at,
        source_name=source_name,
        confidence="demo" if source_mode.casefold() == "demo" else "imported",
        source_mode=source_mode,
        games=((str(item["game_name"]),) if item.get("game_name") else ()),
    )


def normalize_snapshot(payload: object) -> ImportedSignals:
    """Validate and normalize schema-v2 or legacy Twitch-shaped snapshots."""

    if not isinstance(payload, dict):
        raise ValueError("GamePulse snapshot must be a JSON object")
    observed_at = str(payload.get("observed_at") or "").strip()
    if not observed_at:
        raise ValueError("GamePulse snapshot requires observed_at")
    source_name = str(payload.get("source_name") or "Imported GamePulse snapshot").strip()
    source_mode = str(payload.get("source_mode") or ("Demo" if "schema_version" not in payload else "Imported")).strip()
    confidence = str(payload.get("confidence") or ("demo" if source_mode.casefold() == "demo" else "imported"))
    raw_games = payload.get("games", [])
    raw_creators = payload.get("creators", payload.get("streamers", []))
    if not isinstance(raw_games, list) or not isinstance(raw_creators, list):
        raise ValueError("snapshot games and creators must be arrays")

    schema_version = int(payload.get("schema_version", 1))
    if schema_version not in {1, SCHEMA_VERSION}:
        raise ValueError(f"unsupported snapshot schema_version {schema_version}")

    games: list[GameSignal] = []
    creators: list[CreatorSignal] = []
    for item in raw_games:
        if not isinstance(item, dict):
            raise ValueError("each snapshot game must be an object")
        games.append(
            _game_v2(item, observed_at=observed_at, source_name=source_name, source_mode=source_mode, confidence=confidence)
            if schema_version == SCHEMA_VERSION
            else _legacy_game(item, observed_at=observed_at, source_name=source_name, source_mode=source_mode)
        )
    for item in raw_creators:
        if not isinstance(item, dict):
            raise ValueError("each snapshot creator must be an object")
        creator = (
            _creator_v2(item, observed_at=observed_at, source_name=source_name, source_mode=source_mode, confidence=confidence)
            if schema_version == SCHEMA_VERSION
            else _legacy_creator(item, observed_at=observed_at, source_name=source_name, source_mode=source_mode)
        )
        if not creator.creator_id:
            raise ValueError("snapshot creator requires creator_id")
        creators.append(creator)

    return ImportedSignals(
        schema_version=schema_version,
        games=SignalSnapshot(source_mode, observed_at, source_name, games, confidence),
        creators=SignalSnapshot(source_mode, observed_at, source_name, creators, confidence),
    )


def load_snapshot(path: Path) -> ImportedSignals:
    return normalize_snapshot(json.loads(path.read_text(encoding="utf-8")))


def import_snapshot(source: Path, destination: Path) -> None:
    """Validate an imported snapshot before copying it into GamePulse storage."""

    payload = json.loads(source.read_text(encoding="utf-8"))
    normalize_snapshot(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

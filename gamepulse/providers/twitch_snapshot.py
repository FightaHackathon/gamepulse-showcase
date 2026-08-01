"""Validation and import helpers for authorized Twitch snapshot exports.

This intentionally accepts user-provided/API-authorized JSON only. It does not
fetch or scrape twitch.tv pages.
"""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED_TOP_LEVEL = {"observed_at", "games", "streamers"}


def validate_snapshot(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Twitch snapshot must be a JSON object")
    missing = REQUIRED_TOP_LEVEL - set(payload)
    if missing:
        raise ValueError(f"Twitch snapshot missing fields: {', '.join(sorted(missing))}")
    if not isinstance(payload["games"], list) or not isinstance(payload["streamers"], list):
        raise ValueError("Twitch snapshot games and streamers must be arrays")
    for item in payload["games"]:
        if not isinstance(item, dict) or not item.get("game_id") or not item.get("name"):
            raise ValueError("Each game requires game_id and name")
    for item in payload["streamers"]:
        if not isinstance(item, dict) or not item.get("streamer_id") or not item.get("name"):
            raise ValueError("Each streamer requires streamer_id and name")
    return payload


def import_snapshot(source: Path, destination: Path) -> None:
    payload = validate_snapshot(json.loads(source.read_text(encoding="utf-8")))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

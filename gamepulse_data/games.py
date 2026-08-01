from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .source_io import optional_float, optional_int, parse_bool, parse_delimited_values


GAME_BRIDGE_FIELDS = {
    "genres": "game_genres",
    "tags": "game_tags",
    "developers": "game_developers",
    "publishers": "game_publishers",
    "categories": "game_categories",
}


def parse_owner_range(value: str | None) -> tuple[int | None, int | None]:
    if not value:
        return None, None
    normalized = value.replace("..", "-")
    parts = [part.strip() for part in normalized.split("-")]
    if len(parts) != 2:
        return None, None
    def parse_bound(part: str) -> int | None:
        digits = re.sub(r"[^0-9]", "", part)
        return int(digits) if digits else None

    return parse_bound(parts[0]), parse_bound(parts[1])


def parse_release_date(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    for date_format in ("%b %d, %Y", "%Y-%m-%d", "%d %b, %Y"):
        try:
            return datetime.strptime(candidate, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _fallback(primary: Any, secondary: Any) -> Any:
    if primary in (None, "", 0, 0.0):
        return secondary
    return primary


def _optional_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return None if text in {"", "0", "[]"} else text


def normalise_game_row(
    row: dict[str, str], steamspy: dict[int, dict[str, str]]
) -> dict[str, Any] | None:
    app_id = optional_int(row.get("AppID"))
    name = (row.get("Name") or "").strip()
    if app_id is None or not name:
        return None

    fallback = steamspy.get(app_id, {})
    positive = _fallback(optional_int(row.get("Positive")), optional_int(fallback.get("positive")))
    negative = _fallback(optional_int(row.get("Negative")), optional_int(fallback.get("negative")))
    owners_low, owners_high = parse_owner_range(row.get("Estimated owners"))
    fallback_low, fallback_high = parse_owner_range(fallback.get("owners"))
    owners_low = _fallback(owners_low, fallback_low)
    owners_high = _fallback(owners_high, fallback_high)
    total_reviews = (positive or 0) + (negative or 0)

    return {
        "steam_app_id": app_id,
        "name": name,
        "release_date": parse_release_date(row.get("Release date")),
        "price_usd": optional_float(row.get("Price")),
        "discount_pct": optional_float(row.get("Discount")),
        "required_age": optional_int(row.get("Required age")),
        "owners_low": owners_low,
        "owners_high": owners_high,
        "peak_ccu": _fallback(optional_int(row.get("Peak CCU")), optional_int(fallback.get("ccu"))),
        "positive_reviews": positive or 0,
        "negative_reviews": negative or 0,
        "total_reviews": total_reviews,
        "review_score": round((positive or 0) / total_reviews, 6) if total_reviews else None,
        "recommendations": optional_int(row.get("Recommendations")),
        "average_playtime_minutes": _fallback(
            optional_int(row.get("Average playtime forever")),
            optional_int(fallback.get("average_forever")),
        ),
        "median_playtime_minutes": _fallback(
            optional_int(row.get("Median playtime forever")),
            optional_int(fallback.get("median_forever")),
        ),
        "windows": parse_bool(row.get("Windows")),
        "mac": parse_bool(row.get("Mac")),
        "linux": parse_bool(row.get("Linux")),
        "metacritic_score": optional_int(row.get("Metacritic score")),
        "header_image_url": _optional_text(row.get("Header image")),
        "website_url": _optional_text(row.get("Website")),
        "short_description": _optional_text(row.get("About the game")),
        "genres": parse_delimited_values(row.get("Genres")),
        "tags": parse_delimited_values(row.get("Tags")),
        "developers": parse_delimited_values(row.get("Developers")),
        "publishers": parse_delimited_values(row.get("Publishers")),
        "categories": parse_delimited_values(row.get("Categories")),
    }


def build_game_bridges(game: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    bridges: dict[str, list[dict[str, Any]]] = {}
    for source_field, output_name in GAME_BRIDGE_FIELDS.items():
        bridges[output_name] = [
            {"steam_app_id": game["steam_app_id"], "value": value}
            for value in game[source_field]
        ]
    return bridges


def game_master_row(game: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in game.items() if key not in GAME_BRIDGE_FIELDS}

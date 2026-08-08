"""Infer explainable Player Mode preferences from a public Steam library."""

from __future__ import annotations

import math

from gamepulse.providers.steam import PlayerLibrary
from gamepulse.recommendations import PlayerPreferences


def _non_negative_number(value) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if math.isfinite(number) and number > 0 else 0.0


def infer_preferences(library: PlayerLibrary, catalog, limit: int = 12) -> PlayerPreferences:
    tag_weights: dict[str, float] = {}
    genre_weights: dict[str, float] = {}
    for item in library.games:
        try:
            app_id = int(item.get("appid"))
            game = catalog.get_game(app_id)
        except (AttributeError, TypeError, ValueError, KeyError):
            continue
        playtime = _non_negative_number(item.get("playtime_forever"))
        recent = _non_negative_number(item.get("playtime_2weeks"))
        weight = max(1.0, math.log1p(playtime) + 0.5 * math.log1p(recent))
        for value in getattr(game, "tags", ()) or ():
            key = str(value).casefold().strip()
            if key:
                tag_weights[key] = tag_weights.get(key, 0.0) + weight
        for value in getattr(game, "genres", ()) or ():
            key = str(value).casefold().strip()
            if key:
                genre_weights[key] = genre_weights.get(key, 0.0) + weight
    tags = tuple(item for item, _ in sorted(tag_weights.items(), key=lambda pair: (-pair[1], pair[0]))[: max(1, limit)])
    genres = tuple(item for item, _ in sorted(genre_weights.items(), key=lambda pair: (-pair[1], pair[0]))[: max(1, limit)])
    return PlayerPreferences(preferred_tags=tags, preferred_genres=genres)

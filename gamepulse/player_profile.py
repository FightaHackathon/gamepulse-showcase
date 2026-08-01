"""Infer explainable Player Mode preferences from a public Steam library."""

from __future__ import annotations

import math

from gamepulse.providers.steam import PlayerLibrary
from gamepulse.recommendations import PlayerPreferences


def infer_preferences(library: PlayerLibrary, catalog, limit: int = 12) -> PlayerPreferences:
    tag_weights: dict[str, float] = {}
    genre_weights: dict[str, float] = {}
    for item in library.games:
        try:
            app_id = int(item.get("appid"))
            game = catalog.get_game(app_id)
        except (AttributeError, TypeError, ValueError, KeyError):
            continue
        playtime = max(0.0, float(item.get("playtime_forever") or 0))
        recent = max(0.0, float(item.get("playtime_2weeks") or 0))
        weight = max(1.0, math.log1p(playtime) + 0.5 * math.log1p(recent))
        for value in getattr(game, "tags", ()):
            key = str(value).casefold().strip()
            if key:
                tag_weights[key] = tag_weights.get(key, 0.0) + weight
        for value in getattr(game, "genres", ()):
            key = str(value).casefold().strip()
            if key:
                genre_weights[key] = genre_weights.get(key, 0.0) + weight
    tags = tuple(item for item, _ in sorted(tag_weights.items(), key=lambda pair: (-pair[1], pair[0]))[: max(1, limit)])
    genres = tuple(item for item, _ in sorted(genre_weights.items(), key=lambda pair: (-pair[1], pair[0]))[: max(1, limit)])
    return PlayerPreferences(preferred_tags=tags, preferred_genres=genres)

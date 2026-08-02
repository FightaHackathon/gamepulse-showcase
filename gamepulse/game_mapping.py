"""Conservative matching between Twitch categories and Steam catalog games."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
import sqlite3
from pathlib import Path
import unicodedata

from gamepulse.database import ensure_twitch_game_mapping_schema


FUZZY_ACCEPT_SCORE = 0.90
FUZZY_CANDIDATE_SCORE = 0.55
FUZZY_AMBIGUITY_MARGIN = 0.03
DEFAULT_MANUAL_ALIASES_PATH = Path(__file__).resolve().parents[1] / "data" / "manual" / "twitch_steam_aliases.json"


@dataclass(frozen=True)
class SteamGame:
    app_id: int
    name: str


@dataclass(frozen=True)
class GameMapping:
    twitch_game_id: str
    twitch_name: str
    steam_app_id: int | None
    steam_name: str | None
    match_method: str
    match_score: float
    manual_verified: bool = False

    @property
    def manual_verification_flag(self) -> bool:
        """Compatibility wording for consumers that want the flag by name."""
        return self.manual_verified

    @property
    def manual_verification(self) -> bool:
        """Short compatibility alias for the manual verification flag."""
        return self.manual_verified

    @property
    def is_reliable(self) -> bool:
        """Whether Steam-derived features may be used for this mapping."""
        if self.steam_app_id is None:
            return False
        return self.manual_verified or (
            self.match_method in {"exact", "fuzzy"}
            and self.match_score >= FUZZY_ACCEPT_SCORE
        )


@dataclass(frozen=True)
class _ManualEntry:
    twitch_game_id: str | None
    twitch_name: str | None
    steam_app_id: int
    steam_name: str | None
    method: str


@dataclass(frozen=True)
class _ManualIndex:
    by_id: dict[str, _ManualEntry]
    by_name: dict[str, _ManualEntry]


def normalize_game_name(value: str) -> str:
    """Normalize display names for conservative exact matching."""
    source = str(value or "").replace("™", "").replace("®", "").replace("℠", "")
    normalized = unicodedata.normalize("NFKC", source).casefold()
    characters = [character if character.isalnum() or character.isspace() else " " for character in normalized]
    return " ".join("".join(characters).split())


def _is_non_full_release(name: str) -> bool:
    tokens = set(normalize_game_name(name).split())
    return bool({"demo", "playtest"} & tokens) or {"play", "test"} <= tokens


def _is_edition_mismatch(left: str, right: str) -> bool:
    edition_tokens = {
        "complete", "definitive", "deluxe", "edition", "enhanced", "gold",
        "goty", "hd", "remaster", "remastered", "ultimate",
    }
    left_tokens = set(normalize_game_name(left).split())
    right_tokens = set(normalize_game_name(right).split())
    return bool((left_tokens ^ right_tokens) & edition_tokens)


def _parse_app_id(value: object) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("manual Twitch-to-Steam mappings require a numeric steam_app_id")
    try:
        app_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("manual Twitch-to-Steam mappings require a numeric steam_app_id") from exc
    if app_id <= 0:
        raise ValueError("manual Twitch-to-Steam mappings require a positive steam_app_id")
    return app_id


def _manual_entry(
    twitch_name: str | None,
    target: object,
    twitch_game_id: str | None,
    method: str,
) -> _ManualEntry:
    if isinstance(target, dict):
        app_id = _parse_app_id(target.get("steam_app_id"))
        steam_name = target.get("steam_name")
        steam_name = str(steam_name).strip() if steam_name else None
    else:
        app_id = _parse_app_id(target)
        steam_name = None
    return _ManualEntry(
        twitch_game_id=str(twitch_game_id) if twitch_game_id else None,
        twitch_name=str(twitch_name).strip() if twitch_name else None,
        steam_app_id=app_id,
        steam_name=steam_name,
        method=method,
    )


def _load_manual_index(path: Path | None) -> _ManualIndex:
    path = Path(path) if path is not None else DEFAULT_MANUAL_ALIASES_PATH
    if not path.exists():
        return _ManualIndex({}, {})
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Twitch-to-Steam alias file must contain a JSON object")

    by_id: dict[str, _ManualEntry] = {}
    by_name: dict[str, _ManualEntry] = {}
    aliases = payload.get("aliases", {})
    if not isinstance(aliases, dict):
        raise ValueError("Twitch-to-Steam aliases must be a JSON object")
    for twitch_name, target in aliases.items():
        entry = _manual_entry(str(twitch_name), target, None, "alias")
        by_name[normalize_game_name(str(twitch_name))] = entry

    mappings = payload.get("mappings", [])
    if not isinstance(mappings, list):
        raise ValueError("Twitch-to-Steam mappings must be a JSON list")
    for item in mappings:
        if not isinstance(item, dict):
            raise ValueError("Each Twitch-to-Steam mapping must be a JSON object")
        twitch_game_id = item.get("twitch_game_id")
        twitch_name = item.get("twitch_name")
        entry = _manual_entry(twitch_name, item, twitch_game_id, "manual")
        if twitch_game_id:
            by_id[str(twitch_game_id)] = entry
        if twitch_name:
            by_name[normalize_game_name(str(twitch_name))] = entry
    return _ManualIndex(by_id, by_name)


def _steam_by_id(steam_games: list[SteamGame]) -> dict[int, SteamGame]:
    return {game.app_id: game for game in steam_games}


def _mapping_from_manual(
    twitch_game_id: str,
    twitch_name: str,
    entry: _ManualEntry,
    steam_games_by_id: dict[int, SteamGame],
) -> GameMapping:
    steam_name = entry.steam_name or (
        steam_games_by_id[entry.steam_app_id].name
        if entry.steam_app_id in steam_games_by_id
        else None
    )
    return GameMapping(
        twitch_game_id,
        twitch_name,
        entry.steam_app_id,
        steam_name,
        entry.method,
        1.0,
        True,
    )


def _unmatched(twitch_game_id: str, twitch_name: str, method: str = "unmatched", score: float = 0.0) -> GameMapping:
    return GameMapping(twitch_game_id, twitch_name, None, None, method, score, False)


def map_twitch_game(
    twitch_game_id: str,
    twitch_name: str,
    steam_games: list[SteamGame] | tuple[SteamGame, ...],
    manual_aliases_path: Path | None = None,
) -> GameMapping:
    """Resolve one Twitch category without forcing an uncertain Steam match."""
    twitch_game_id = str(twitch_game_id)
    twitch_name = str(twitch_name)
    manual = _load_manual_index(manual_aliases_path)
    steam_games = [SteamGame(int(game.app_id), str(game.name)) for game in steam_games]
    steam_games_by_id = _steam_by_id(steam_games)

    manual_entry = manual.by_id.get(twitch_game_id) or manual.by_name.get(normalize_game_name(twitch_name))
    if manual_entry:
        return _mapping_from_manual(twitch_game_id, twitch_name, manual_entry, steam_games_by_id)

    if _is_non_full_release(twitch_name):
        return _unmatched(twitch_game_id, twitch_name, "excluded")

    normalized_name = normalize_game_name(twitch_name)
    exact_candidates = [
        game for game in steam_games
        if normalize_game_name(game.name) == normalized_name and not _is_non_full_release(game.name)
    ]
    if len(exact_candidates) == 1:
        game = exact_candidates[0]
        return GameMapping(twitch_game_id, twitch_name, game.app_id, game.name, "exact", 1.0, False)
    if len(exact_candidates) > 1:
        return _unmatched(twitch_game_id, twitch_name, "ambiguous")

    candidates = []
    for game in steam_games:
        if _is_non_full_release(game.name) or _is_edition_mismatch(twitch_name, game.name):
            continue
        score = SequenceMatcher(None, normalized_name, normalize_game_name(game.name)).ratio()
        if score >= FUZZY_CANDIDATE_SCORE:
            candidates.append((score, game))
    if not candidates:
        return _unmatched(twitch_game_id, twitch_name)
    candidates.sort(key=lambda item: (-item[0], item[1].app_id))
    best_score, best_game = candidates[0]
    if len(candidates) > 1 and best_score - candidates[1][0] < FUZZY_AMBIGUITY_MARGIN:
        return _unmatched(twitch_game_id, twitch_name, "ambiguous", best_score)
    return GameMapping(twitch_game_id, twitch_name, best_game.app_id, best_game.name, "fuzzy", best_score, False)


def map_twitch_games(
    twitch_games: list[object] | tuple[object, ...],
    steam_games: list[SteamGame] | tuple[SteamGame, ...],
    manual_aliases_path: Path | None = None,
) -> list[GameMapping]:
    """Map Twitch provider rows while preserving their source ordering."""
    mappings = []
    for game in twitch_games:
        if isinstance(game, dict):
            game_id = game.get("game_id")
            name = game.get("name")
        else:
            game_id = getattr(game, "game_id")
            name = getattr(game, "name")
        mappings.append(map_twitch_game(game_id, name, steam_games, manual_aliases_path))
    return mappings


def load_steam_games(connection: sqlite3.Connection) -> list[SteamGame]:
    """Read only the Steam catalog names needed by the resolver."""
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'games'"
    ).fetchone()
    if not exists:
        return []
    return [SteamGame(int(row[0]), str(row[1])) for row in connection.execute("SELECT steam_app_id, name FROM games")]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def persist_game_mappings(
    connection: sqlite3.Connection,
    mappings: list[GameMapping] | tuple[GameMapping, ...],
    updated_at: str | None = None,
) -> int:
    """Persist mappings without allowing automatic rows to replace manual rows."""
    ensure_twitch_game_mapping_schema(connection)
    updated_at = updated_at or _now_iso()
    persisted = 0
    for mapping in mappings:
        existing = connection.execute(
            "SELECT manual_verified FROM twitch_game_mappings WHERE twitch_game_id = ?",
            (mapping.twitch_game_id,),
        ).fetchone()
        if existing and bool(existing[0]) and not mapping.manual_verified:
            continue
        values = (
            mapping.twitch_game_id,
            mapping.twitch_name,
            mapping.steam_app_id,
            mapping.steam_name,
            mapping.match_method,
            mapping.match_score,
            int(mapping.manual_verified),
            updated_at,
        )
        if existing:
            connection.execute(
                """UPDATE twitch_game_mappings SET twitch_name = ?, steam_app_id = ?, steam_name = ?,
                   match_method = ?, match_score = ?, manual_verified = ?, updated_at = ?
                   WHERE twitch_game_id = ?""",
                values[1:] + (values[0],),
            )
        else:
            connection.execute(
                """INSERT INTO twitch_game_mappings (
                    twitch_game_id, twitch_name, steam_app_id, steam_name, match_method,
                    match_score, manual_verified, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
        persisted += 1
    return persisted


def load_game_mappings(
    connection: sqlite3.Connection,
    twitch_game_ids: list[str] | tuple[str, ...] | None = None,
) -> dict[str, GameMapping]:
    """Load persisted mappings for applying only reliable Steam joins."""
    ensure_twitch_game_mapping_schema(connection)
    if twitch_game_ids:
        placeholders = ",".join("?" for _ in twitch_game_ids)
        rows = connection.execute(
            f"SELECT twitch_game_id, twitch_name, steam_app_id, steam_name, match_method, match_score, manual_verified "
            f"FROM twitch_game_mappings WHERE twitch_game_id IN ({placeholders})",
            tuple(twitch_game_ids),
        )
    else:
        rows = connection.execute(
            "SELECT twitch_game_id, twitch_name, steam_app_id, steam_name, match_method, match_score, manual_verified "
            "FROM twitch_game_mappings"
        )
    return {
        str(row[0]): GameMapping(
            str(row[0]), str(row[1]), int(row[2]) if row[2] is not None else None,
            str(row[3]) if row[3] is not None else None, str(row[4]), float(row[5]), bool(row[6])
        )
        for row in rows
    }

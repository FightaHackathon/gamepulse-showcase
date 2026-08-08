"""Environment-backed settings for the local GamePulse desktop app."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _path_setting(root: Path, name: str, default: str) -> Path:
    raw = os.getenv(name, default).strip() or default
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _provider_mode(name: str) -> str:
    value = os.getenv(name, "auto").strip().casefold() or "auto"
    if name == "GAME_SIGNAL_PROVIDER":
        allowed = {"auto", "steam", "public", "snapshot", "imported", "twitch"}
    elif name == "CREATOR_PROVIDER":
        allowed = {"auto", "directory", "snapshot", "imported", "twitch"}
    else:
        allowed = {"auto"}
    return value if value in allowed else "auto"


@dataclass(frozen=True)
class Settings:
    root: Path
    processed_dir: Path
    database_path: Path
    gamepulse_snapshot_path: Path
    creator_directory_path: Path
    twitch_demo_snapshot: Path
    twitch_manual_snapshot: Path
    external_cache_path: Path
    game_signal_provider: str = "auto"
    creator_provider: str = "auto"
    twitch_client_id: str | None = None
    twitch_client_secret: str | None = None
    steam_web_api_key: str | None = None
    mistral_api_key: str | None = None
    streamscharts_client_id: str | None = None
    streamscharts_token: str | None = None

    @classmethod
    def from_env(cls, root: Path) -> "Settings":
        load_dotenv(root / ".env", override=False)
        processed_dir = (
            root
            / "data"
            / "processed"
            / os.getenv("GAMEPULSE_PROCESSED_DATE", "2026-08-01")
        )
        return cls(
            root=root,
            processed_dir=processed_dir,
            database_path=_path_setting(
                root,
                "GAMEPULSE_DATABASE_PATH",
                "data/prototype/gamepulse_prototype.sqlite3",
            ),
            gamepulse_snapshot_path=_path_setting(
                root,
                "GAMEPULSE_SNAPSHOT_PATH",
                "data/demo/gamepulse_snapshot.json",
            ),
            creator_directory_path=_path_setting(
                root,
                "CREATOR_DIRECTORY_PATH",
                "data/manual/creators.csv",
            ),
            twitch_demo_snapshot=_path_setting(
                root,
                "TWITCH_DEMO_SNAPSHOT_PATH",
                "data/demo/twitch_snapshot.json",
            ),
            twitch_manual_snapshot=_path_setting(
                root,
                "TWITCH_SNAPSHOT_PATH",
                "data/manual/twitch_snapshot.json",
            ),
            external_cache_path=_path_setting(
                root,
                "GAMEPULSE_EXTERNAL_CACHE_PATH",
                "data/cache/external-provider-cache.json",
            ),
            game_signal_provider=_provider_mode("GAME_SIGNAL_PROVIDER"),
            creator_provider=_provider_mode("CREATOR_PROVIDER"),
            twitch_client_id=_optional("TWITCH_CLIENT_ID"),
            twitch_client_secret=_optional("TWITCH_CLIENT_SECRET"),
            steam_web_api_key=_optional("STEAM_WEB_API_KEY"),
            mistral_api_key=_optional("MISTRAL_API_KEY"),
            streamscharts_client_id=_optional("STREAMSCHARTS_CLIENT_ID"),
            streamscharts_token=_optional("STREAMSCHARTS_TOKEN"),
        )

    @property
    def twitch_enabled(self) -> bool:
        return bool(self.twitch_client_id and self.twitch_client_secret)

    @property
    def twitch_snapshot_path(self) -> Path:
        """Legacy Twitch fallback path retained for the optional provider."""

        return (
            self.twitch_manual_snapshot
            if self.twitch_manual_snapshot.exists()
            else self.twitch_demo_snapshot
        )

    @property
    def steam_enabled(self) -> bool:
        return bool(self.steam_web_api_key)

    @property
    def mistral_enabled(self) -> bool:
        return bool(self.mistral_api_key)

    @property
    def streamscharts_enabled(self) -> bool:
        return bool(self.streamscharts_client_id and self.streamscharts_token)

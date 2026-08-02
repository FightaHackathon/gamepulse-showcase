"""Environment-backed settings for the local GamePulse prototype."""

import json
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _secrets_file_available(root: Path | None = None) -> bool:
    candidates: list[Path] = []
    try:
        candidates.append(Path.home() / ".streamlit" / "secrets.toml")
    except RuntimeError:
        # Tests and controlled data jobs may intentionally clear home-related
        # environment variables.
        pass
    if root is not None:
        candidates.append(root / ".streamlit" / "secrets.toml")
    if any(path.is_file() for path in candidates):
        return True

    # Streamlit keeps its loaded secrets object in the module namespace. Read
    # that namespace directly so checking for an already-loaded store does not
    # invoke the warning-producing lazy parser when no file is present.
    streamlit = sys.modules.get("streamlit")
    secret_store = getattr(streamlit, "__dict__", {}).get("secrets") if streamlit else None
    if isinstance(secret_store, Mapping) and not hasattr(secret_store, "_file_paths"):
        return True
    return getattr(secret_store, "_secrets", None) is not None


def _optional(name: str, root: Path | None = None) -> str | None:
    """Read an optional credential from local env or Streamlit Cloud secrets.

    Streamlit Community Cloud exposes configured values through ``st.secrets``
    rather than process environment variables.  Keep environment variables as
    the first choice so local ``.env`` development and existing deployments
    retain their current behavior.
    """
    value = os.getenv(name, "").strip()
    if not value:
        try:
            # ``app.py`` imports Streamlit before constructing Settings. Do
            # not import it from command-line data scripts just to discover
            # that no Cloud secrets are present.
            streamlit = sys.modules.get("streamlit")
            value = str(streamlit.secrets.get(name, "")).strip() if streamlit and _secrets_file_available(root) else ""
        except Exception:
            # Streamlit is optional for data-preparation scripts and may not
            # have a secrets file outside an app runtime.
            value = ""
    return value or None


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return default
    return min(maximum, value)


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return default
    return min(maximum, value)


@dataclass(frozen=True)
class Settings:
    root: Path
    processed_dir: Path
    database_path: Path
    demo_config_path: Path
    twitch_demo_snapshot: Path
    twitch_manual_snapshot: Path
    twitch_client_id: str | None = None
    twitch_client_secret: str | None = None
    steam_web_api_key: str | None = None
    mistral_api_key: str | None = None
    twitch_max_stream_pages: int = 3
    twitch_request_timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls, root: Path) -> "Settings":
        load_dotenv(root / ".env", override=False)
        processed_dir = root / "data" / "processed" / os.getenv("GAMEPULSE_PROCESSED_DATE", "2026-08-01")
        return cls(
            root=root,
            processed_dir=processed_dir,
            database_path=root / "data" / "prototype" / "gamepulse_prototype.sqlite3",
            demo_config_path=root / "data" / "prototype" / "demo_config.json",
            twitch_demo_snapshot=root / "data" / "demo" / "twitch_snapshot.json",
            twitch_manual_snapshot=Path(os.getenv("TWITCH_SNAPSHOT_PATH", "")) if os.getenv("TWITCH_SNAPSHOT_PATH", "").strip() else root / "data" / "manual" / "twitch_snapshot.json",
            twitch_client_id=_optional("TWITCH_CLIENT_ID", root),
            twitch_client_secret=_optional("TWITCH_CLIENT_SECRET", root),
            steam_web_api_key=_optional("STEAM_WEB_API_KEY", root),
            mistral_api_key=_optional("MISTRAL_API_KEY", root),
            twitch_max_stream_pages=_bounded_int("TWITCH_MAX_STREAM_PAGES", 3, 1, 10),
            twitch_request_timeout_seconds=_bounded_float("TWITCH_REQUEST_TIMEOUT_SECONDS", 15.0, 1.0, 120.0),
        )

    @property
    def demo_selected_app_id(self) -> int | None:
        """Return the curated prototype game when its config is valid."""
        try:
            payload = json.loads(self.demo_config_path.read_text(encoding="utf-8"))
            selected_app_id = payload["selected_app_id"]
            return int(selected_app_id)
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            return None

    @property
    def twitch_enabled(self) -> bool:
        return bool(self.twitch_client_id and self.twitch_client_secret)

    @property
    def twitch_snapshot_path(self) -> Path:
        """Use an explicitly imported/authorized snapshot when available."""
        return self.twitch_manual_snapshot if self.twitch_manual_snapshot.exists() else self.twitch_demo_snapshot

    @property
    def steam_enabled(self) -> bool:
        return bool(self.steam_web_api_key)

    @property
    def mistral_enabled(self) -> bool:
        return bool(self.mistral_api_key)

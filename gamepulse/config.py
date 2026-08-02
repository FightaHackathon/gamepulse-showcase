"""Environment-backed settings for the local GamePulse prototype."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _optional(name: str) -> str | None:
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
            value = str(streamlit.secrets.get(name, "")).strip() if streamlit else ""
        except Exception:
            # Streamlit is optional for data-preparation scripts and may not
            # have a secrets file outside an app runtime.
            value = ""
    return value or None


@dataclass(frozen=True)
class Settings:
    root: Path
    processed_dir: Path
    database_path: Path
    twitch_demo_snapshot: Path
    twitch_manual_snapshot: Path
    twitch_client_id: str | None = None
    twitch_client_secret: str | None = None
    steam_web_api_key: str | None = None
    mistral_api_key: str | None = None

    @classmethod
    def from_env(cls, root: Path) -> "Settings":
        load_dotenv(root / ".env", override=False)
        processed_dir = root / "data" / "processed" / os.getenv("GAMEPULSE_PROCESSED_DATE", "2026-08-01")
        return cls(
            root=root,
            processed_dir=processed_dir,
            database_path=root / "data" / "prototype" / "gamepulse_prototype.sqlite3",
            twitch_demo_snapshot=root / "data" / "demo" / "twitch_snapshot.json",
            twitch_manual_snapshot=Path(os.getenv("TWITCH_SNAPSHOT_PATH", "")) if os.getenv("TWITCH_SNAPSHOT_PATH", "").strip() else root / "data" / "manual" / "twitch_snapshot.json",
            twitch_client_id=_optional("TWITCH_CLIENT_ID"),
            twitch_client_secret=_optional("TWITCH_CLIENT_SECRET"),
            steam_web_api_key=_optional("STEAM_WEB_API_KEY"),
            mistral_api_key=_optional("MISTRAL_API_KEY"),
        )

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

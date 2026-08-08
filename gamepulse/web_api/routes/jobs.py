from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy.orm import Session

from gamepulse.db.session import make_engine
from gamepulse.providers.steam_public import SteamCurrentPlayersProvider
from gamepulse.providers.steamspy import SteamSpyProvider
from gamepulse.providers.twitchtracker import TwitchTrackerProvider
from gamepulse.services.snapshot_refresh import RefreshReport, SnapshotRefreshService
from gamepulse.web_api.settings import WebSettings


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def run_refresh(settings: WebSettings) -> RefreshReport:
    engine = make_engine(settings.database_url)
    try:
        with Session(engine) as session:
            providers = [
                SteamCurrentPlayersProvider(timeout_seconds=settings.provider_timeout_seconds),
                TwitchTrackerProvider(timeout_seconds=settings.provider_timeout_seconds),
                SteamSpyProvider(timeout_seconds=settings.provider_timeout_seconds),
            ]
            return SnapshotRefreshService(session, providers).refresh_catalog()
    finally:
        engine.dispose()


@router.get("/refresh")
def refresh_job(authorization: str | None = Header(default=None)) -> dict:
    settings = WebSettings()
    expected = f"Bearer {settings.cron_secret}" if settings.cron_secret else None
    if expected is None or authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return asdict(run_refresh(settings))

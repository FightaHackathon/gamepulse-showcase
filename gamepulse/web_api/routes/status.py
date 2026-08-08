from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from gamepulse.db.repositories import ProviderStatusRepository
from gamepulse.web_api.dependencies import get_db_session
from gamepulse.web_api.schemas.common import SourceStatusResponse, SourcesResponse


router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("/sources", response_model=SourcesResponse)
def get_source_status(session: Session = Depends(get_db_session)) -> SourcesResponse:
    statuses = ProviderStatusRepository(session).list_statuses(stale_hours=48)
    return SourcesResponse(
        sources=[SourceStatusResponse(**asdict(status)) for status in statuses]
    )

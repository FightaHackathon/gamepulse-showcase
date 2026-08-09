from __future__ import annotations

import inspect
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from pydantic_core import ValidationError
from sqlalchemy.orm import Session

from gamepulse.player_session import empty_profile_session
from gamepulse.providers.steam import PlayerLibrary, SteamProvider, SteamProviderError
from gamepulse.services.player_recommendations import PlayerRecommendationService
from gamepulse.web_api.dependencies import get_db_session


router = APIRouter(prefix="/api/player", tags=["player"])

# Keep legacy discovery useful for the UI while bounded pages can reach 400 results.
DISCOVERY_RESULT_LIMIT = 80
PLAYER_PAGE_SIZE = 100
PLAYER_MAX_PAGE = 3


class PlayerAnalyzeRequest(BaseModel):
    """Accept both the original profile_url contract and Fusion's explicit name."""

    steam_profile_url: str | None = Field(default=None, min_length=1)
    profile_url: str | None = Field(default=None, min_length=1)
    steam_web_api_key: str | None = None
    page: int | None = Field(default=None, ge=0, le=PLAYER_MAX_PAGE)

    @model_validator(mode="after")
    def require_profile(self):
        if not (self.steam_profile_url or self.profile_url):
            raise ValueError("steam_profile_url or profile_url is required")
        return self

    @property
    def profile(self) -> str:
        return str(self.steam_profile_url or self.profile_url).strip()


def player_service(session: Session) -> PlayerRecommendationService:
    return PlayerRecommendationService(session)


def get_player_session() -> Iterator[Session | None]:
    """Keep the legacy provider-only request usable before web storage is configured."""

    try:
        yield from get_db_session()
    except ValidationError as exc:
        if "database_url" not in str(exc):
            raise
        yield None


def _service_for(session: Session):
    """Keep the old zero-argument monkeypatch seam used by the prototype tests."""

    try:
        parameter_count = len(inspect.signature(player_service).parameters)
    except (TypeError, ValueError):
        parameter_count = 1
    return player_service() if parameter_count == 0 else player_service(session)


def _serialize_result(item) -> dict:
    breakdown = item.breakdown
    return {
        "app_id": item.app_id,
        "steam_app_id": item.app_id,
        "name": item.name,
        "score": item.score,
        "personal_fit": round(float(breakdown.personal_fit), 4),
        "review_score": item.review_score,
        "header_image_url": item.header_image_url,
        "current_players": item.current_players,
        "peak_ccu": item.peak_ccu,
        "release_date": item.release_date,
        "trend_change": item.trend_change,
        "owned": item.owned,
        "tags": list(item.tags),
        "genres": list(item.genres),
        "breakdown": {
            "personal_fit": round(float(breakdown.personal_fit), 4),
            "review_quality": None if breakdown.review_quality is None else round(float(breakdown.review_quality), 4),
            "current_activity": None if breakdown.current_activity is None else round(float(breakdown.current_activity), 4),
            "trend_momentum": None if breakdown.trend_momentum is None else round(float(breakdown.trend_momentum), 4),
        },
        "factor_breakdown": {
            "personal_fit": {"score": round(float(breakdown.personal_fit), 4), "weight": 45},
            "reviews": {"score": None if breakdown.review_quality is None else round(float(breakdown.review_quality), 4), "weight": 20},
            "activity": {"score": None if breakdown.current_activity is None else round(float(breakdown.current_activity), 4), "weight": 15},
            "momentum": {"score": None if breakdown.trend_momentum is None else round(float(breakdown.trend_momentum), 4), "weight": 20},
        },
        "steam_store_url": f"https://store.steampowered.com/app/{item.app_id}",
        "explanation": "; ".join(item.reasons),
    }


def _catalog_fallback() -> PlayerLibrary:
    return PlayerLibrary(steam_id="profile-not-fetched", games=(), source_name="GamePulse catalogue fallback", complete=False)


@router.post("/analyze")
def analyze_player(
    request: PlayerAnalyzeRequest,
    session: Session | None = Depends(get_player_session),
    steam_key_header: str | None = Header(default=None, alias="X-GamePulse-Steam-Key"),
):
    # The key exists only in this stack frame. It is never placed into a model,
    # response, log line, browser payload, or database row.
    request_key = request.steam_web_api_key or steam_key_header
    use_profile_provider = request.steam_profile_url is not None or request.profile_url is not None or request_key is not None
    library = _catalog_fallback()
    if use_profile_provider:
        provider = SteamProvider(request_key)
        try:
            steam_id = provider.resolve_profile(request.profile)
            library = provider.get_library(steam_id)
        except (ValueError, SteamProviderError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    service = _service_for(session) if session is not None else _service_for_without_database()
    if request.page is None:
        owned, discovery = service.recommend(library, limit_owned=10, limit_discovery=DISCOVERY_RESULT_LIMIT)
        paging = None
    else:
        owned, discovery, has_more = service.recommend(
            library,
            limit_owned=10,
            limit_discovery=PLAYER_PAGE_SIZE,
            catalog_offset=request.page * PLAYER_PAGE_SIZE,
            return_page_info=True,
        )
        paging = {
            "page": request.page,
            "page_size": PLAYER_PAGE_SIZE,
            "has_more": bool(has_more and request.page < PLAYER_MAX_PAGE),
            "next_page": request.page + 1 if has_more and request.page < PLAYER_MAX_PAGE else None,
        }
    recommendations = [_serialize_result(item) for item in [*owned, *discovery]]
    body = {
        "recommendations": recommendations,
        "profile": request.profile,
        "steam_id": library.steam_id,
        "library_complete": library.complete,
        "source_name": library.source_name,
    }
    if request.profile_url is not None:
        body["owned_recommendations"] = [_serialize_result(item) for item in owned]
        body["discovery_recommendations"] = [_serialize_result(item) for item in discovery]
    if paging is not None:
        body["paging"] = paging
    return body


def _service_for_without_database():
    """Return a patched legacy service when no database is configured."""

    try:
        return player_service()
    except TypeError as exc:
        raise HTTPException(status_code=503, detail="GamePulse database is not configured") from exc

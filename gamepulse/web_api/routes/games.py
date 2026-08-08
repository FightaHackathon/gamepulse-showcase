from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from gamepulse.db.repositories import GameRepository, SnapshotRepository
from gamepulse.web_api.dependencies import get_db_session
from gamepulse.web_api.schemas.common import GameDetailResponse, HistoryResponse, MetricResponse


router = APIRouter(prefix="/api/games", tags=["games"])


def _metric_response(point) -> MetricResponse:
    return MetricResponse(**asdict(point))


@router.get("/{app_id}", response_model=GameDetailResponse)
def get_game(app_id: int, session: Session = Depends(get_db_session)) -> GameDetailResponse:
    game = GameRepository(session).get_game(app_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    metrics = [
        _metric_response(point)
        for point in SnapshotRepository(session).latest_metrics_for_game(app_id)
    ]
    return GameDetailResponse(
        steam_app_id=game.steam_app_id,
        name=game.name,
        release_date=game.release_date,
        price_usd=game.price_usd,
        owners_low=game.owners_low,
        owners_high=game.owners_high,
        peak_ccu=game.peak_ccu,
        total_reviews=game.total_reviews,
        review_score=game.review_score,
        header_image_url=game.header_image_url,
        short_description=game.short_description,
        tags=list(game.tags),
        genres=list(game.genres),
        steam_store_url=game.steam_store_url,
        metrics=metrics,
    )


@router.get("/{app_id}/history", response_model=HistoryResponse)
def get_game_history(
    app_id: int,
    metric: str = Query(min_length=1, max_length=96),
    limit: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(get_db_session),
) -> HistoryResponse:
    if GameRepository(session).get_game(app_id) is None:
        raise HTTPException(status_code=404, detail="Game not found")

    points = [
        _metric_response(point)
        for point in SnapshotRepository(session).history_for_game(app_id, metric, limit)
    ]
    return HistoryResponse(steam_app_id=app_id, metric=metric, points=points)

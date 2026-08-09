from __future__ import annotations

from dataclasses import asdict
from math import isfinite

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gamepulse.db.repositories import GameRepository, MetricPoint, SnapshotRepository
from gamepulse.db.models import ReviewModel
from gamepulse.trend_artifact import load_trend_artifact
from gamepulse.providers.steam_public import SteamCurrentPlayersProvider
from gamepulse.providers.twitchtracker import TwitchTrackerProvider
from gamepulse.services.snapshot_refresh import SnapshotRefreshService
from gamepulse.web_api.dependencies import get_db_session
from gamepulse.web_api.settings import WebSettings
from gamepulse.web_api.schemas.common import GameDetailResponse, HistoryResponse, MetricResponse, ReviewExcerptsResponse


router = APIRouter(prefix="/api/games", tags=["games"])


def _metric_response(point) -> MetricResponse:
    return MetricResponse(**asdict(point))


def _review_excerpts_for_game(session: Session, app_id: int) -> ReviewExcerptsResponse:
    def select_excerpts(recommended: bool):
        rows = session.scalars(
            select(ReviewModel)
            .where(
                ReviewModel.steam_app_id == int(app_id),
                ReviewModel.recommended.is_(recommended),
                ReviewModel.source_mode == "public_store_api",
                # Steam's review API language filter is part of the stored
                # provenance URL. Exclude older/imported rows that were not
                # fetched with the explicit English-only query.
                func.lower(func.coalesce(ReviewModel.source_url, "")).like("%language=english%"),
                func.length(func.trim(ReviewModel.review_text)) > 0,
            )
            .order_by(
                func.coalesce(ReviewModel.helpful_votes, -1).desc(),
                func.coalesce(ReviewModel.created_at_unix, -1).desc(),
                ReviewModel.review_id.asc(),
            )
            .limit(3)
        ).all()
        return [
            {
                "text": row.review_text,
                "helpful_votes": row.helpful_votes,
                "created_at_unix": row.created_at_unix,
            }
            for row in rows
        ]

    return ReviewExcerptsResponse(positive=select_excerpts(True), negative=select_excerpts(False))


_ARTIFACT_METRICS = {
    ("player", "current_players"): "steam",
    ("player", "peak_ccu"): "steam",
    ("streamer", "average_viewers_30d"): "streaming",
}


def _artifact_metrics_for_game(app_id: int, cached_metrics: list[MetricPoint]) -> list[MetricPoint]:
    """Expose direct artifact components only for metrics without usable snapshots."""

    cached_values = {
        point.metric
        for point in cached_metrics
        if point.value_numeric is not None and isfinite(float(point.value_numeric))
    }
    artifact = load_trend_artifact()
    fallback: list[MetricPoint] = []
    for (audience, metric), signal_type in _ARTIFACT_METRICS.items():
        if metric in cached_values:
            continue
        row = artifact.get((int(app_id), audience))
        if row is None:
            continue
        value = row.components.get(metric)
        if value is None:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue
        if not isfinite(numeric_value):
            continue
        fallback.append(
            MetricPoint(
                metric=metric,
                value_numeric=numeric_value,
                value_text=None,
                observed_at=row.observed_at,
                source_name=row.source_name,
                source_mode=row.source_mode,
                confidence=row.confidence,
                source_url=None,
                signal_type=signal_type,
            )
        )
    return fallback


@router.get("/{app_id}", response_model=GameDetailResponse)
def get_game(app_id: int, refresh: bool = Query(default=False), session: Session = Depends(get_db_session)) -> GameDetailResponse:
    game = GameRepository(session).get_game(app_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    refresh_status = "not_requested"
    refresh_providers = []
    if refresh:
        settings = WebSettings()
        report = SnapshotRefreshService(
            session,
            [
                SteamCurrentPlayersProvider(timeout_seconds=settings.provider_timeout_seconds),
                TwitchTrackerProvider(timeout_seconds=settings.provider_timeout_seconds),
            ],
        ).refresh_game(app_id)
        refresh_status = report.status
        refresh_providers = [
            {
                "provider_name": item.provider_name,
                "status": item.status,
                "metrics_written": item.metrics_written,
                "error": item.error,
            }
            for item in report.provider_runs
        ]

    cached_metrics = SnapshotRepository(session).latest_metrics_for_game(app_id)
    metrics = [_metric_response(point) for point in [*cached_metrics, *_artifact_metrics_for_game(app_id, cached_metrics)]]
    return GameDetailResponse(
        steam_app_id=game.steam_app_id,
        name=game.name,
        release_date=game.release_date,
        price_usd=game.price_usd,
        owners_low=game.owners_low,
        owners_high=game.owners_high,
        peak_ccu=game.peak_ccu,
        positive_reviews=game.positive_reviews,
        negative_reviews=game.negative_reviews,
        total_reviews=game.total_reviews,
        review_score=game.review_score,
        header_image_url=game.header_image_url,
        short_description=game.short_description,
        tags=list(game.tags),
        genres=list(game.genres),
        steam_store_url=game.steam_store_url,
        metrics=metrics,
        review_excerpts=_review_excerpts_for_game(session, app_id),
        refresh_status=refresh_status,
        refresh_providers=refresh_providers,
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

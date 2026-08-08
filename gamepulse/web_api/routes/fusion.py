from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from gamepulse.db.models import GameModel, SteamSnapshotModel, StreamingSnapshotModel, TrendScoreModel
from gamepulse.db.repositories import GameRepository
from gamepulse.trend_artifact import load_trend_artifact
from gamepulse.web_api.dependencies import get_db_session


router = APIRouter(prefix="/api", tags=["fusion"])


class StreamerSimulationRequest(BaseModel):
    mode: str = "balanced"
    genres: list[str] = Field(default_factory=list)

    @field_validator("mode")
    @classmethod
    def normalize_mode(cls, value: str) -> str:
        normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
        aliases = {"audience": "audience_potential", "reach": "audience_potential", "discoverability": "discoverability", "balanced_growth": "balanced"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"balanced", "discoverability", "audience_potential"}:
            raise ValueError("mode must be balanced, discoverability, or audience_potential")
        return normalized


class ConceptRequest(BaseModel):
    direction: str = Field(min_length=1, max_length=160)
    opportunity_app_id: int | None = None


def _latest_values(session: Session, app_id: int, model, metrics: set[str]) -> dict[str, float]:
    rows = session.scalars(
        select(model)
        .where(model.steam_app_id == app_id, model.metric.in_(metrics))
        .order_by(model.observed_at.desc(), model.id.desc())
    ).all()
    values: dict[str, float] = {}
    for row in rows:
        if row.metric not in values and row.value_numeric is not None:
            values[row.metric] = max(0.0, float(row.value_numeric))
    return values


def _normalized(values: list[float]) -> list[float]:
    maximum = max(values, default=0.0)
    if maximum <= 0:
        return [0.0 for _ in values]
    return [max(0.0, min(1.0, value / maximum)) for value in values]


def _latest_trend(session: Session, app_id: int, audience: str) -> TrendScoreModel | None:
    trend = session.scalars(
        select(TrendScoreModel)
        .where(TrendScoreModel.steam_app_id == app_id, TrendScoreModel.audience == audience)
        .order_by(TrendScoreModel.observed_at.desc(), TrendScoreModel.id.desc())
    ).first()
    return trend or load_trend_artifact().get((app_id, audience))


def _normalized_component(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1.0:
        number /= 100.0
    return max(0.0, min(1.0, number))


def _streamer_rows(session: Session, request: StreamerSimulationRequest) -> list[dict]:
    games = GameRepository(session).list_games(limit=200)
    requested_genres = {value.casefold().strip() for value in request.genres if value.strip()}
    candidates = [game for game in games if not requested_genres or requested_genres.intersection({genre.casefold() for genre in game.genres})]
    rows: list[dict] = []
    for game in candidates:
        stream = _latest_values(session, game.steam_app_id, StreamingSnapshotModel, {"average_viewers_30d", "viewer_count", "channel_count", "category_growth", "growth_pct"})
        steam = _latest_values(session, game.steam_app_id, SteamSnapshotModel, {"current_players", "peak_ccu"})
        trend = _latest_trend(session, game.steam_app_id, "streamer") or _latest_trend(session, game.steam_app_id, "player")
        components = trend.components if trend is not None else {}
        viewers = stream.get("average_viewers_30d", stream.get("viewer_count", float(game.peak_ccu or 0)))
        channels = stream.get("channel_count", max(1.0, viewers / 50.0 if viewers else 1.0))
        ratio = viewers / max(channels, 1.0)
        growth = stream.get("category_growth", stream.get("growth_pct", float(components.get("growth", 0.0))))
        if growth > 1:
            growth /= 100.0
        momentum = _normalized_component(components.get("momentum", trend.score if trend is not None else None)) or 0.0
        rows.append({"game": game, "viewers": viewers, "channels": channels, "ratio": ratio, "growth": max(0.0, min(1.0, growth)), "momentum": max(0.0, min(1.0, momentum))})

    demand = _normalized([row["viewers"] for row in rows])
    ratios = _normalized([row["ratio"] for row in rows])
    channels = _normalized([row["channels"] for row in rows])
    for row, demand_score, ratio_score, channel_score in zip(rows, demand, ratios, channels):
        competition_score = 1.0 - channel_score
        if request.mode == "discoverability":
            score = demand_score * 0.1 + competition_score * 0.3 + ratio_score * 0.35 + row["momentum"] * 0.1 + row["growth"] * 0.15
        elif request.mode == "audience_potential":
            score = demand_score * 0.45 + competition_score * 0.1 + ratio_score * 0.2 + row["momentum"] * 0.1 + row["growth"] * 0.15
        else:
            score = demand_score * 0.25 + competition_score * 0.15 + ratio_score * 0.25 + row["momentum"] * 0.15 + row["growth"] * 0.2
        row["result"] = {
            "steam_app_id": row["game"].steam_app_id,
            "name": row["game"].name,
            "header_image_url": row["game"].header_image_url,
            "steam_store_url": row["game"].steam_store_url,
            "opportunity_score": round(score * 100, 1),
            "breakdown": {
                "viewer_demand": round(demand_score * 100, 1),
                "creator_competition": round(competition_score * 100, 1),
                "viewer_channel_ratio": round(ratio_score * 100, 1),
                "steam_momentum": round(row["momentum"] * 100, 1),
                "category_growth": round(row["growth"] * 100, 1),
            },
            "evidence": [
                f"{int(row['viewers']):,} cached viewers or player-demand observations",
                f"{int(row['channels']):,} estimated creator channels",
                f"{row['ratio']:.1f} viewers per channel",
            ],
            "reason": "Balanced public-signal estimate from cached snapshots; this is a new-streamer simulation, not a Twitch-channel forecast.",
        }
    rows.sort(key=lambda row: (-row["result"]["opportunity_score"], row["game"].name.casefold(), row["game"].steam_app_id))
    return [row["result"] for row in rows]


@router.post("/streamer/simulate")
def streamer_simulate(request: StreamerSimulationRequest, session: Session = Depends(get_db_session)):
    return {"simulator": True, "mode": request.mode, "recommendations": _streamer_rows(session, request)}


def _developer_evidence(session: Session, game) -> tuple[list[str], dict[str, float]]:
    steam = _latest_values(session, game.steam_app_id, SteamSnapshotModel, {"current_players", "peak_ccu"})
    stream = _latest_values(session, game.steam_app_id, StreamingSnapshotModel, {"average_viewers_30d", "viewer_count", "channel_count", "category_growth", "growth_pct"})
    trend = _latest_trend(session, game.steam_app_id, "developer") or _latest_trend(session, game.steam_app_id, "player")
    components = trend.components if trend is not None else {}
    players = steam.get("current_players", float(game.peak_ccu or 0))
    viewers = stream.get("average_viewers_30d", stream.get("viewer_count", 0.0))
    channels = stream.get("channel_count", 0.0)
    growth_value = components.get("growth", components.get("player_growth_pct"))
    growth_value = growth_value if growth_value is not None else stream.get("category_growth", stream.get("growth_pct"))
    growth = float(growth_value or 0.0)
    if growth > 1:
        growth /= 100.0
    sentiment = float(game.review_score or 0.0)
    saturation = max(0.0, min(1.0, channels / 1000.0))
    genre_demand = _normalized_component(components.get("genre_demand"))
    opportunity_gap = _normalized_component(components.get("opportunity_gap"))
    review_sentiment = _normalized_component(components.get("review_sentiment")) or sentiment
    legacy_score = players / max(players, 1000.0) * 25 + viewers / max(viewers, 5000.0) * 25 + max(0.0, min(1.0, growth)) * 20 + sentiment * 20 + (1 - saturation) * 10
    intelligence_parts = [(genre_demand, 0.30), (opportunity_gap, 0.35), (review_sentiment, 0.35)]
    available_intelligence = [(value, weight) for value, weight in intelligence_parts if value is not None]
    intelligence_score = None
    if available_intelligence:
        total_weight = sum(weight for _, weight in available_intelligence)
        intelligence_score = sum(value * weight for value, weight in available_intelligence) / total_weight * 100
    score = legacy_score if intelligence_score is None else max(0.0, min(100.0, 0.55 * legacy_score + 0.45 * intelligence_score))
    evidence = [
        f"Rising genres: {', '.join(game.genres) or 'unclassified'}",
        f"Player activity signal: {int(players):,} current or peak players",
        f"Streaming demand signal: {int(viewers):,} cached viewers",
        f"Creator saturation: {int(channels):,} observed channels",
        f"Review sentiment: {sentiment:.0%} positive-share estimate",
        f"Genre demand signal: {genre_demand:.0%}" if genre_demand is not None else "Genre demand signal: unavailable",
        f"Opportunity gap: {opportunity_gap:.0%}" if opportunity_gap is not None else "Opportunity gap: unavailable",
    ]
    return evidence, {
        "player_growth": round(max(0.0, min(1.0, growth)) * 100, 1),
        "streaming_demand": round(min(1.0, viewers / max(viewers, 5000.0)) * 100, 1),
        "saturation": round(saturation * 100, 1),
        "review_sentiment": round(review_sentiment * 100, 1),
        "genre_demand": None if genre_demand is None else round(genre_demand * 100, 1),
        "opportunity_gap": None if opportunity_gap is None else round(opportunity_gap * 100, 1),
        "opportunity_score": round(score, 1),
    }


@router.get("/developer/opportunities")
def developer_opportunities(session: Session = Depends(get_db_session)):
    opportunities = []
    for game in GameRepository(session).list_games(limit=100):
        evidence, signals = _developer_evidence(session, game)
        opportunities.append({"steam_app_id": game.steam_app_id, "name": game.name, "genre": list(game.genres), "score": signals["opportunity_score"], "signals": signals, "evidence": evidence, "steam_store_url": game.steam_store_url, "header_image_url": game.header_image_url})
    opportunities.sort(key=lambda item: (-item["score"], item["name"].casefold(), item["steam_app_id"]))
    return {"opportunities": opportunities}


@router.post("/developer/concept")
def developer_concept(request: ConceptRequest, session: Session = Depends(get_db_session)):
    games = GameRepository(session).list_games(limit=100)
    if not games:
        raise HTTPException(status_code=404, detail="No market opportunities available")
    selected = next((game for game in games if request.opportunity_app_id == game.steam_app_id), None)
    selected = selected or next((game for game in games if request.direction.casefold() in " ".join((*game.genres, *game.tags)).casefold()), games[0])
    evidence, signals = _developer_evidence(session, selected)
    idea = {
        "title": f"{request.direction.strip().title()} Signal",
        "genre": request.direction.strip(),
        "gameplay_loop": "Scout a changing arena, build a short-lived advantage, then extract before the next market shift.",
        "mechanics": ["short-session progression", "risk-and-reward extraction", "cooperative role synergies"],
        "target_player": "Players who want readable strategy and meaningful progress in 20–30 minute sessions.",
        "multiplayer_or_solo": "Solo with optional 2–4 player co-op",
        "steam_price_range": "$14.99–$24.99",
        "comparable_games": [selected.name, *list(selected.tags)[:2]],
        "opportunity_score": signals["opportunity_score"],
        "risks": ["Direction may compete for attention in a saturated genre.", "Public snapshots are directional and do not verify sales."],
    }
    return {
        "title": idea["title"],
        "genre": idea["genre"],
        "gameplay_loop": idea["gameplay_loop"],
        "target_player": idea["target_player"],
        "evidence": evidence,
        "ai_generated": True,
        "data_evidence": {"selected_game": selected.name, "signals": signals, "observations": evidence},
        "ai_generated_idea": idea,
    }

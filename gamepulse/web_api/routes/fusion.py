from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from gamepulse.db.repositories import GameRepository, SnapshotRepository
from gamepulse.web_api.dependencies import get_db_session

router = APIRouter(prefix="/api", tags=["fusion"])


class PlayerAnalyzeRequest(BaseModel):
    steam_profile_url: str
    steam_web_api_key: str | None = None


class StreamerSimulationRequest(BaseModel):
    mode: str = "balanced"
    genres: list[str] = []


class ConceptRequest(BaseModel):
    direction: str


@router.post("/player/analyze")
def player_analyze(request: PlayerAnalyzeRequest, session: Session = Depends(get_db_session)):
    games = GameRepository(session).list_games(limit=10)
    return {
        "profile": request.steam_profile_url,
        "recommendations": [
            {
                "steam_app_id": game.steam_app_id,
                "name": game.name,
                "personal_fit": 45,
                "review_score": game.review_score,
                "steam_store_url": game.steam_store_url,
                "explanation": "Recommended from available GamePulse signals.",
            }
            for game in games
        ],
    }


@router.post("/streamer/simulate")
def streamer_simulate(request: StreamerSimulationRequest, session: Session = Depends(get_db_session)):
    games = GameRepository(session).list_games(limit=10)
    return {
        "mode": request.mode,
        "recommendations": [
            {
                "steam_app_id": game.steam_app_id,
                "name": game.name,
                "opportunity_score": 50,
                "reason": "Based on cached gaming market signals.",
            }
            for game in games
        ],
    }


@router.get("/developer/opportunities")
def developer_opportunities(session: Session = Depends(get_db_session)):
    games = GameRepository(session).list_games(limit=20)
    return {
        "opportunities": [
            {
                "steam_app_id": game.steam_app_id,
                "name": game.name,
                "genre": list(game.genres),
                "signals": ["reviews", "activity", "market"],
            }
            for game in games
        ]
    }


@router.post("/developer/concept")
def developer_concept(request: ConceptRequest):
    return {
        "title": f"{request.direction} Concept",
        "genre": request.direction,
        "gameplay_loop": "Core gameplay loop generated from market opportunity.",
        "target_player": "PC Steam players",
        "evidence": [],
        "ai_generated": True,
    }

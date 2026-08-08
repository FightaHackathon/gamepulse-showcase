from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamepulse.db.models import GameGenreModel, GameModel, GameTagModel, SteamSnapshotModel
from gamepulse.providers.steam import PlayerLibrary


@dataclass(frozen=True)
class PlayerScoreBreakdown:
    personal_fit: float
    review_quality: float | None
    current_activity: float | None
    trend_momentum: float | None


@dataclass(frozen=True)
class PlayerRecommendationResult:
    app_id: int
    name: str
    score: int
    breakdown: PlayerScoreBreakdown
    reasons: tuple[str, ...]
    owned: bool
    header_image_url: str | None = None
    price_usd: float | None = None
    review_score: float | None = None
    current_players: int | None = None
    trend_change: float | None = None


@dataclass(frozen=True)
class _Candidate:
    app_id: int
    name: str
    tags: tuple[str, ...]
    genres: tuple[str, ...]
    header_image_url: str | None
    price_usd: float | None
    review_score: float | None


class PlayerRecommendationService:
    """Rank owned and discovery games with four transparent Player factors."""

    WEIGHTS = {
        "personal_fit": 0.45,
        "review_quality": 0.20,
        "current_activity": 0.15,
        "trend_momentum": 0.20,
    }

    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _bounded(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _review_quality(value: float | None) -> float | None:
        if value is None:
            return None
        number = float(value)
        if number > 1.0:
            number /= 100.0
        return PlayerRecommendationService._bounded(number)

    def _catalog(self) -> list[_Candidate]:
        models = self.session.scalars(select(GameModel).order_by(GameModel.steam_app_id)).all()
        tags: dict[int, list[str]] = defaultdict(list)
        genres: dict[int, list[str]] = defaultdict(list)
        for app_id, value in self.session.execute(
            select(GameTagModel.steam_app_id, GameTagModel.value).order_by(GameTagModel.steam_app_id, GameTagModel.value)
        ):
            tags[int(app_id)].append(str(value))
        for app_id, value in self.session.execute(
            select(GameGenreModel.steam_app_id, GameGenreModel.value).order_by(GameGenreModel.steam_app_id, GameGenreModel.value)
        ):
            genres[int(app_id)].append(str(value))
        return [
            _Candidate(
                app_id=model.steam_app_id,
                name=model.name,
                tags=tuple(tags.get(model.steam_app_id, ())),
                genres=tuple(genres.get(model.steam_app_id, ())),
                header_image_url=model.header_image_url,
                price_usd=model.price_usd,
                review_score=model.review_score,
            )
            for model in models
        ]

    @staticmethod
    def _preference_weights(
        library: PlayerLibrary,
        by_id: dict[int, _Candidate],
    ) -> tuple[dict[str, float], dict[str, float]]:
        tag_weights: dict[str, float] = defaultdict(float)
        genre_weights: dict[str, float] = defaultdict(float)
        for item in library.games:
            try:
                app_id = int(item.get("appid"))
            except (AttributeError, TypeError, ValueError):
                continue
            game = by_id.get(app_id)
            if game is None:
                continue
            try:
                playtime = max(0.0, float(item.get("playtime_forever") or 0))
                recent = max(0.0, float(item.get("playtime_2weeks") or 0))
            except (AttributeError, TypeError, ValueError):
                playtime = recent = 0.0
            weight = max(1.0, math.log1p(playtime) + 0.5 * math.log1p(recent))
            for value in game.tags:
                key = value.casefold().strip()
                if key:
                    tag_weights[key] += weight
            for value in game.genres:
                key = value.casefold().strip()
                if key:
                    genre_weights[key] += weight
        return dict(tag_weights), dict(genre_weights)

    @staticmethod
    def _dimension_fit(values: tuple[str, ...], weights: dict[str, float], top_n: int) -> float | None:
        if not weights:
            return None
        strongest = sorted(weights.values(), reverse=True)[: max(1, top_n)]
        denominator = sum(strongest)
        if denominator <= 0:
            return None
        matched = sum(weights.get(value.casefold().strip(), 0.0) for value in values)
        return PlayerRecommendationService._bounded(matched / denominator)

    @classmethod
    def _personal_fit(cls, game: _Candidate, tag_weights: dict[str, float], genre_weights: dict[str, float]) -> float:
        tag_fit = cls._dimension_fit(game.tags, tag_weights, 3)
        genre_fit = cls._dimension_fit(game.genres, genre_weights, 2)
        available: list[tuple[float, float]] = []
        if tag_fit is not None:
            available.append((tag_fit, 0.65))
        if genre_fit is not None:
            available.append((genre_fit, 0.35))
        if not available:
            return 0.0
        return sum(value * weight for value, weight in available) / sum(weight for _, weight in available)

    def _activity(self) -> dict[int, tuple[int | None, float | None, float | None]]:
        rows = self.session.scalars(
            select(SteamSnapshotModel)
            .where(SteamSnapshotModel.metric == "current_players")
            .order_by(SteamSnapshotModel.steam_app_id, SteamSnapshotModel.observed_at, SteamSnapshotModel.id)
        ).all()
        history: dict[int, list[float]] = defaultdict(list)
        for row in rows:
            if row.value_numeric is not None:
                history[int(row.steam_app_id)].append(max(0.0, float(row.value_numeric)))

        latest_values = [values[-1] for values in history.values() if values]
        maximum = max(latest_values, default=0.0)
        log_max = math.log1p(maximum) if maximum > 0 else 0.0
        result: dict[int, tuple[int | None, float | None, float | None]] = {}
        for app_id, values in history.items():
            if not values:
                continue
            latest = values[-1]
            activity = math.log1p(latest) / log_max if log_max > 0 else None
            change = None
            momentum = None
            if len(values) >= 2:
                first = values[0]
                change = (latest - first) / max(abs(first), 1.0)
                momentum = 0.5 + 0.5 * math.tanh(change)
            result[app_id] = (
                int(round(latest)),
                None if activity is None else self._bounded(activity),
                None if momentum is None else self._bounded(momentum),
            )
        return result

    @classmethod
    def _score(cls, breakdown: PlayerScoreBreakdown) -> int:
        factors = {
            "personal_fit": breakdown.personal_fit,
            "review_quality": breakdown.review_quality,
            "current_activity": breakdown.current_activity,
            "trend_momentum": breakdown.trend_momentum,
        }
        available = [(factors[name], weight) for name, weight in cls.WEIGHTS.items() if factors[name] is not None]
        if not available:
            return 0
        weighted = sum(float(value) * weight for value, weight in available)
        total_weight = sum(weight for _, weight in available)
        return max(0, min(100, round(weighted / total_weight * 100)))

    @staticmethod
    def _reasons(breakdown: PlayerScoreBreakdown) -> tuple[str, ...]:
        evidence: list[tuple[float, str]] = []
        evidence.append((breakdown.personal_fit, "strong match for your most-played tags and genres"))
        if breakdown.review_quality is not None:
            evidence.append((breakdown.review_quality, "strong Steam review quality"))
        if breakdown.current_activity is not None:
            evidence.append((breakdown.current_activity, "healthy current player activity"))
        if breakdown.trend_momentum is not None:
            direction = "player activity is trending upward" if breakdown.trend_momentum >= 0.5 else "player activity is currently softer"
            evidence.append((breakdown.trend_momentum, direction))
        evidence.sort(key=lambda item: item[0], reverse=True)
        reasons = [text for value, text in evidence if value >= 0.5][:3]
        return tuple(reasons or ["matches the available GamePulse evidence"])

    def recommend(
        self,
        library: PlayerLibrary,
        limit_owned: int = 10,
        limit_discovery: int = 10,
    ) -> tuple[list[PlayerRecommendationResult], list[PlayerRecommendationResult]]:
        catalog = self._catalog()
        by_id = {game.app_id: game for game in catalog}
        owned_ids: set[int] = set()
        for item in library.games:
            try:
                owned_ids.add(int(item.get("appid")))
            except (AttributeError, TypeError, ValueError):
                continue

        tag_weights, genre_weights = self._preference_weights(library, by_id)
        activity = self._activity()
        ranked: list[PlayerRecommendationResult] = []
        for game in catalog:
            current_players, current_activity, trend_momentum = activity.get(game.app_id, (None, None, None))
            breakdown = PlayerScoreBreakdown(
                personal_fit=self._personal_fit(game, tag_weights, genre_weights),
                review_quality=self._review_quality(game.review_score),
                current_activity=current_activity,
                trend_momentum=trend_momentum,
            )
            score = self._score(breakdown)
            values = activity.get(game.app_id)
            trend_change = None
            if values is not None and trend_momentum is not None:
                rows = self.session.scalars(
                    select(SteamSnapshotModel)
                    .where(
                        SteamSnapshotModel.steam_app_id == game.app_id,
                        SteamSnapshotModel.metric == "current_players",
                        SteamSnapshotModel.value_numeric.is_not(None),
                    )
                    .order_by(SteamSnapshotModel.observed_at, SteamSnapshotModel.id)
                ).all()
                if len(rows) >= 2:
                    first = float(rows[0].value_numeric or 0)
                    latest = float(rows[-1].value_numeric or 0)
                    trend_change = (latest - first) / max(abs(first), 1.0)
            ranked.append(
                PlayerRecommendationResult(
                    app_id=game.app_id,
                    name=game.name,
                    score=score,
                    breakdown=breakdown,
                    reasons=self._reasons(breakdown),
                    owned=game.app_id in owned_ids,
                    header_image_url=game.header_image_url,
                    price_usd=game.price_usd,
                    review_score=game.review_score,
                    current_players=current_players,
                    trend_change=trend_change,
                )
            )

        ranked.sort(key=lambda item: (-item.score, item.name.casefold(), item.app_id))
        owned = [item for item in ranked if item.owned][: max(0, int(limit_owned))]
        discovery = [item for item in ranked if not item.owned][: max(0, int(limit_discovery))]
        return owned, discovery

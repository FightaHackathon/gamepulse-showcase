from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamepulse.db.models import GameGenreModel, GameModel, GameTagModel, SteamSnapshotModel
from gamepulse.providers.steam import PlayerLibrary
from gamepulse.trend_artifact import load_peak_ccu_artifact


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
    peak_ccu: int | None = None
    trend_change: float | None = None
    release_date: str | None = None
    tags: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Candidate:
    app_id: int
    name: str
    tags: tuple[str, ...]
    genres: tuple[str, ...]
    header_image_url: str | None
    price_usd: float | None
    review_score: float | None
    release_date: str | None
    catalog_peak_ccu: int | None


class PlayerRecommendationService:
    """Rank owned and discovery games with four transparent Player factors."""

    DISCOVERY_CATALOG_LIMIT = 100
    MAX_DISCOVERY_PAGES = 4
    HIDDEN_TAGS = frozenset({"video production"})

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

    @classmethod
    def _visible_tags(cls, values: list[str]) -> tuple[str, ...]:
        return tuple(value for value in values if value.casefold().strip() not in cls.HIDDEN_TAGS)

    @staticmethod
    def _review_quality(value: float | None) -> float | None:
        if value is None:
            return None
        number = float(value)
        if number > 1.0:
            number /= 100.0
        return PlayerRecommendationService._bounded(number)

    def _catalog(
        self,
        owned_ids: set[int],
        offset: int = 0,
        limit: int = DISCOVERY_CATALOG_LIMIT,
        include_owned_context: bool = True,
    ) -> tuple[list[_Candidate], bool]:
        requested_limit = max(1, int(limit))
        page_offset = max(0, int(offset))
        recent_limit = max(1, (requested_limit * 2 + 4) // 5)
        # Read separate recent, popular, and broad catalog slices. The
        # catalog slice restores coverage for older games while the first two
        # slices keep current/popular titles visible.
        popular_limit = max(1, (requested_limit * 2 + 4) // 5)
        # Every candidate is a Neon game row. Combine recent releases with a
        # popularity slice so established games such as Counter-Strike remain
        # visible alongside newer releases.
        recent_models = self.session.scalars(
            select(GameModel)
            .order_by(GameModel.release_date.desc().nullslast(), GameModel.steam_app_id)
            .offset(page_offset)
            .limit(recent_limit)
        ).all()
        popular_models = self.session.scalars(
            select(GameModel)
            .order_by(
                GameModel.peak_ccu.desc().nullslast(),
                GameModel.owners_high.desc().nullslast(),
                GameModel.total_reviews.desc().nullslast(),
                GameModel.steam_app_id,
            )
            .offset(page_offset)
            .limit(popular_limit)
        ).all()
        catalog_models = self.session.scalars(
            select(GameModel)
            .order_by(GameModel.steam_app_id)
            .offset(page_offset)
            .limit(requested_limit)
        ).all()
        models = []
        seen_model_ids: set[int] = set()
        for model in [*recent_models, *popular_models, *catalog_models]:
            if model.steam_app_id not in seen_model_ids:
                models.append(model)
                seen_model_ids.add(model.steam_app_id)
            if len(models) >= requested_limit:
                break
        page_has_more = len(models) == requested_limit and page_offset < (self.MAX_DISCOVERY_PAGES - 1) * requested_limit
        known_ids = {model.steam_app_id for model in models}
        missing_owned_ids = owned_ids.difference(known_ids) if include_owned_context else set()
        if missing_owned_ids:
            models.extend(
                self.session.scalars(
                    select(GameModel)
                    .where(GameModel.steam_app_id.in_(missing_owned_ids))
                    .order_by(GameModel.release_date.desc().nullslast(), GameModel.steam_app_id)
                    .limit(min(requested_limit, max(1, requested_limit - len(known_ids) + 1)))
                ).all()
            )
            while len(models) > requested_limit:
                removable = next((model for model in reversed(models) if model.steam_app_id not in owned_ids), None)
                if removable is None:
                    removable = models[-1]
                models.remove(removable)
        models.sort(key=lambda model: model.steam_app_id)
        models.sort(key=lambda model: model.release_date or "", reverse=True)
        app_ids = [model.steam_app_id for model in models]
        tags: dict[int, list[str]] = defaultdict(list)
        genres: dict[int, list[str]] = defaultdict(list)
        for app_id, value in self.session.execute(
            select(GameTagModel.steam_app_id, GameTagModel.value)
            .where(GameTagModel.steam_app_id.in_(app_ids))
            .order_by(GameTagModel.steam_app_id, GameTagModel.value)
        ):
            tags[int(app_id)].append(str(value))
        for app_id, value in self.session.execute(
            select(GameGenreModel.steam_app_id, GameGenreModel.value)
            .where(GameGenreModel.steam_app_id.in_(app_ids))
            .order_by(GameGenreModel.steam_app_id, GameGenreModel.value)
        ):
            genres[int(app_id)].append(str(value))
        return [
            _Candidate(
                app_id=model.steam_app_id,
                name=model.name,
                tags=self._visible_tags(tags.get(model.steam_app_id, [])),
                genres=tuple(genres.get(model.steam_app_id, ())),
                header_image_url=model.header_image_url,
                price_usd=model.price_usd,
                review_score=model.review_score,
                release_date=model.release_date,
                catalog_peak_ccu=None if model.peak_ccu is None else int(model.peak_ccu),
            )
            for model in models
        ], page_has_more

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
        # A catalog row without tags should not be penalized for missing a
        # dimension; renormalize around the genres it actually provides.
        if tag_fit is not None and game.tags:
            available.append((tag_fit, 0.65))
        if genre_fit is not None and game.genres:
            available.append((genre_fit, 0.35))
        if not available:
            return 0.0
        return sum(value * weight for value, weight in available) / sum(weight for _, weight in available)

    def _activity(self, app_ids: list[int]) -> dict[int, tuple[int | None, float | None, float | None, float | None]]:
        if not app_ids:
            return {}
        rows = self.session.scalars(
            select(SteamSnapshotModel)
            .where(
                SteamSnapshotModel.steam_app_id.in_(app_ids),
                SteamSnapshotModel.metric == "current_players",
            )
            .order_by(SteamSnapshotModel.steam_app_id, SteamSnapshotModel.observed_at, SteamSnapshotModel.id)
        ).all()
        history: dict[int, list[float]] = defaultdict(list)
        for row in rows:
            if row.value_numeric is not None:
                history[int(row.steam_app_id)].append(max(0.0, float(row.value_numeric)))

        latest_values = [values[-1] for values in history.values() if values]
        maximum = max(latest_values, default=0.0)
        log_max = math.log1p(maximum) if maximum > 0 else 0.0
        result: dict[int, tuple[int | None, float | None, float | None, float | None]] = {}
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
                change,
            )
        return result

    def _peak_ccu(self, app_ids: list[int]) -> dict[int, int]:
        if not app_ids:
            return {}
        rows = self.session.scalars(
            select(SteamSnapshotModel)
            .where(
                SteamSnapshotModel.steam_app_id.in_(app_ids),
                SteamSnapshotModel.metric == "peak_ccu",
                SteamSnapshotModel.value_numeric.is_not(None),
            )
            .order_by(SteamSnapshotModel.steam_app_id, SteamSnapshotModel.observed_at.desc(), SteamSnapshotModel.id.desc())
        ).all()
        values: dict[int, int] = {}
        for row in rows:
            values.setdefault(int(row.steam_app_id), int(round(float(row.value_numeric))))
        artifact = load_peak_ccu_artifact()
        for app_id in app_ids:
            if app_id in values:
                continue
            if app_id in artifact:
                values[app_id] = artifact[app_id]
        return values

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
        normalized = weighted / total_weight
        if len(available) == 1:
            # A personal match without review/activity evidence is useful but
            # should not look as certain as a fully observed recommendation.
            normalized = normalized * 0.75 + 0.5 * 0.25
        return max(0, min(100, round(normalized * 100)))

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

    @staticmethod
    def _owned_match_reason(game: _Candidate, owned_games: list[_Candidate]) -> str | None:
        matches: list[tuple[int, str, list[str]]] = []
        game_tags = {value.casefold(): value for value in game.tags}
        game_genres = {value.casefold(): value for value in game.genres}
        for owned in owned_games:
            shared = [game_genres[key] for key in game_genres.keys() & {value.casefold() for value in owned.genres}]
            shared += [game_tags[key] for key in game_tags.keys() & {value.casefold() for value in owned.tags}]
            if shared:
                matches.append((len(shared), owned.name, sorted(set(shared), key=str.casefold)))
        if not matches:
            return None
        matches.sort(key=lambda item: (-item[0], item[1].casefold()))
        names = ", ".join(item[1] for item in matches[:2])
        shared = ", ".join(matches[0][2][:3])
        return f"shares {shared} with your owned game{'' if len(matches) == 1 else 's'}: {names}"

    def recommend(
        self,
        library: PlayerLibrary,
        limit_owned: int = 10,
        limit_discovery: int = 80,
        catalog_offset: int | None = None,
        return_page_info: bool = False,
    ) -> tuple[list[PlayerRecommendationResult], list[PlayerRecommendationResult]] | tuple[list[PlayerRecommendationResult], list[PlayerRecommendationResult], bool]:
        owned_ids: set[int] = set()
        for item in library.games:
            try:
                owned_ids.add(int(item.get("appid")))
            except (AttributeError, TypeError, ValueError):
                continue

        catalog, page_has_more = self._catalog(
            owned_ids,
            offset=0 if catalog_offset is None else catalog_offset,
            limit=self.DISCOVERY_CATALOG_LIMIT,
            include_owned_context=catalog_offset is None,
        )
        by_id = {game.app_id: game for game in catalog}
        tag_weights, genre_weights = self._preference_weights(library, by_id)
        owned_context = [game for game in catalog if game.app_id in owned_ids]
        activity = self._activity([game.app_id for game in catalog])
        peak_ccu = self._peak_ccu([game.app_id for game in catalog])
        ranked: list[PlayerRecommendationResult] = []
        for game in catalog:
            current_players, current_activity, trend_momentum, trend_change = activity.get(game.app_id, (None, None, None, None))
            breakdown = PlayerScoreBreakdown(
                personal_fit=self._personal_fit(game, tag_weights, genre_weights),
                review_quality=self._review_quality(game.review_score),
                current_activity=current_activity,
                trend_momentum=trend_momentum,
            )
            score = self._score(breakdown)
            reasons = list(self._reasons(breakdown))
            if not game.app_id in owned_ids:
                match_reason = self._owned_match_reason(game, owned_context)
                if match_reason:
                    reasons.insert(0, match_reason)
            ranked.append(
                PlayerRecommendationResult(
                    app_id=game.app_id,
                    name=game.name,
                    score=score,
                    breakdown=breakdown,
                    reasons=tuple(reasons[:3]),
                    owned=game.app_id in owned_ids,
                    header_image_url=game.header_image_url,
                    price_usd=game.price_usd,
                    review_score=game.review_score,
                    current_players=current_players,
                    peak_ccu=peak_ccu.get(game.app_id, game.catalog_peak_ccu),
                    trend_change=trend_change,
                    release_date=game.release_date,
                    tags=game.tags,
                    genres=game.genres,
                )
            )

        # Keep personal fit as the primary rank, then use available popularity
        # and release recency to break ties among similarly fitting games.
        ranked.sort(key=lambda item: (item.name.casefold(), item.app_id))
        ranked.sort(key=lambda item: item.release_date or "", reverse=True)
        ranked.sort(key=lambda item: max(item.current_players or 0, item.peak_ccu or 0), reverse=True)
        ranked.sort(key=lambda item: item.score, reverse=True)
        owned = [item for item in ranked if item.owned][: max(0, int(limit_owned))]
        discovery = [item for item in ranked if not item.owned][: max(0, int(limit_discovery))]
        if return_page_info:
            return owned, discovery, page_has_more
        return owned, discovery

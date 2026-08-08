from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import GameGenreModel, GameModel, GameTagModel, SteamSnapshotModel, StreamingSnapshotModel


@dataclass(frozen=True)
class GameRecord:
    steam_app_id: int
    name: str
    release_date: str | None
    price_usd: float | None
    owners_low: int | None
    owners_high: int | None
    peak_ccu: int | None
    total_reviews: int | None
    review_score: float | None
    header_image_url: str | None
    short_description: str | None
    tags: tuple[str, ...]
    genres: tuple[str, ...]

    @property
    def steam_store_url(self) -> str:
        return f"https://store.steampowered.com/app/{self.steam_app_id}"


@dataclass(frozen=True)
class MetricPoint:
    metric: str
    value_numeric: float | None
    value_text: str | None
    observed_at: datetime
    source_name: str
    source_mode: str
    confidence: str
    source_url: str | None
    signal_type: str


@dataclass(frozen=True)
class GameSignalSnapshot:
    steam_app_id: int
    signal_type: str
    metric: str
    value_numeric: float | None
    value_text: str | None
    observed_at: datetime
    source_name: str
    source_mode: str
    confidence: str
    source_url: str | None = None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class GameRepository:
    def __init__(self, session: Session):
        self.session = session

    def _record(self, model: GameModel) -> GameRecord:
        tags = tuple(
            self.session.scalars(
                select(GameTagModel.value)
                .where(GameTagModel.steam_app_id == model.steam_app_id)
                .order_by(GameTagModel.value)
            )
        )
        genres = tuple(
            self.session.scalars(
                select(GameGenreModel.value)
                .where(GameGenreModel.steam_app_id == model.steam_app_id)
                .order_by(GameGenreModel.value)
            )
        )
        return GameRecord(
            steam_app_id=model.steam_app_id,
            name=model.name,
            release_date=model.release_date,
            price_usd=model.price_usd,
            owners_low=model.owners_low,
            owners_high=model.owners_high,
            peak_ccu=model.peak_ccu,
            total_reviews=model.total_reviews,
            review_score=model.review_score,
            header_image_url=model.header_image_url,
            short_description=model.short_description,
            tags=tags,
            genres=genres,
        )

    def get_game(self, app_id: int) -> GameRecord | None:
        model = self.session.get(GameModel, int(app_id))
        return self._record(model) if model is not None else None

    def list_games(self, limit: int = 50, offset: int = 0) -> list[GameRecord]:
        bounded_limit = max(1, min(int(limit), 500))
        bounded_offset = max(0, int(offset))
        models = self.session.scalars(
            select(GameModel)
            .order_by(GameModel.name, GameModel.steam_app_id)
            .limit(bounded_limit)
            .offset(bounded_offset)
        ).all()
        return [self._record(model) for model in models]


class SnapshotRepository:
    _MODELS = {
        "steam": SteamSnapshotModel,
        "streaming": StreamingSnapshotModel,
    }

    def __init__(self, session: Session):
        self.session = session

    @classmethod
    def _model(cls, signal_type: str):
        try:
            return cls._MODELS[signal_type]
        except KeyError as exc:
            raise ValueError(f"unsupported signal type: {signal_type}") from exc

    @staticmethod
    def _snapshot(row, signal_type: str) -> GameSignalSnapshot:
        return GameSignalSnapshot(
            steam_app_id=int(row.steam_app_id),
            signal_type=signal_type,
            metric=row.metric,
            value_numeric=row.value_numeric,
            value_text=row.value_text,
            observed_at=_aware(row.observed_at),
            source_name=row.source_name,
            source_mode=row.source_mode,
            confidence=row.confidence,
            source_url=row.source_url,
        )

    @staticmethod
    def _point(row, signal_type: str) -> MetricPoint:
        return MetricPoint(
            metric=row.metric,
            value_numeric=row.value_numeric,
            value_text=row.value_text,
            observed_at=_aware(row.observed_at),
            source_name=row.source_name,
            source_mode=row.source_mode,
            confidence=row.confidence,
            source_url=row.source_url,
            signal_type=signal_type,
        )

    def latest_for_game(self, app_id: int) -> GameSignalSnapshot | None:
        candidates: list[GameSignalSnapshot] = []
        for signal_type, model in self._MODELS.items():
            row = self.session.scalars(
                select(model)
                .where(model.steam_app_id == int(app_id))
                .order_by(model.observed_at.desc(), model.id.desc())
                .limit(1)
            ).first()
            if row is not None:
                candidates.append(self._snapshot(row, signal_type))
        return max(candidates, key=lambda item: item.observed_at) if candidates else None

    def history_for_game(self, app_id: int, metric: str, limit: int = 100) -> list[MetricPoint]:
        bounded_limit = max(1, min(int(limit), 1000))
        points: list[MetricPoint] = []
        for signal_type, model in self._MODELS.items():
            rows = self.session.scalars(
                select(model)
                .where(model.steam_app_id == int(app_id), model.metric == metric)
                .order_by(model.observed_at.desc(), model.id.desc())
                .limit(bounded_limit)
            ).all()
            points.extend(self._point(row, signal_type) for row in rows)
        points.sort(key=lambda item: item.observed_at)
        return points[-bounded_limit:]

    def upsert_snapshot(self, snapshot: GameSignalSnapshot) -> None:
        model = self._model(snapshot.signal_type)
        row = self.session.scalars(
            select(model).where(
                model.steam_app_id == snapshot.steam_app_id,
                model.metric == snapshot.metric,
                model.observed_at == snapshot.observed_at,
                model.source_name == snapshot.source_name,
            )
        ).first()
        values = {
            "value_numeric": snapshot.value_numeric,
            "value_text": snapshot.value_text,
            "source_mode": snapshot.source_mode,
            "confidence": snapshot.confidence,
            "source_url": snapshot.source_url,
        }
        if row is None:
            row = model(
                steam_app_id=snapshot.steam_app_id,
                metric=snapshot.metric,
                observed_at=snapshot.observed_at,
                source_name=snapshot.source_name,
                **values,
            )
            self.session.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        self.session.commit()

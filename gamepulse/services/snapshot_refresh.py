from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamepulse.db.models import ProviderRunModel, ReviewModel, SteamSnapshotModel, SteamSpySnapshotModel, StreamingSnapshotModel
from gamepulse.db.repositories import GameRepository
from gamepulse.providers.contracts import GameIdentity, GameSignalProvider, ProviderMetric, ReviewExcerpt


@dataclass(frozen=True)
class ProviderRunResult:
    provider_name: str
    status: str
    metrics_written: int
    error: str | None = None


@dataclass(frozen=True)
class RefreshReport:
    status: str
    games_considered: int
    metrics_written: int
    provider_runs: tuple[ProviderRunResult, ...]


class SnapshotRefreshService:
    """Refresh external game signals into durable cached snapshots.

    Frontend requests never call providers directly. Successful provider data is
    committed independently so a later provider failure cannot erase useful data.
    """

    def __init__(
        self,
        session: Session,
        providers: Iterable[GameSignalProvider],
        *,
        clock=None,
    ):
        self.session = session
        self.providers = tuple(providers)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _games(self, limit: int | None) -> list:
        repository = GameRepository(self.session)
        if limit is not None:
            return repository.list_games(limit=max(1, int(limit)), offset=0)
        games = []
        offset = 0
        while True:
            batch = repository.list_games(limit=500, offset=offset)
            if not batch:
                break
            games.extend(batch)
            if len(batch) < 500:
                break
            offset += len(batch)
        return games

    @staticmethod
    def _split_value(metric: ProviderMetric) -> tuple[float | None, str | None]:
        if metric.value is None:
            return None, None
        if isinstance(metric.value, bool):
            return float(metric.value), None
        if isinstance(metric.value, (int, float)):
            return float(metric.value), None
        return None, str(metric.value)

    def _persist_regular(self, signal_type: str, game: GameIdentity, metric: ProviderMetric) -> None:
        model = SteamSnapshotModel if signal_type == "steam" else StreamingSnapshotModel
        filters = [
            model.steam_app_id == game.steam_app_id,
            model.metric == metric.metric,
            model.observed_at == metric.observed_at,
            model.source_name == metric.source_name,
        ]
        row = self.session.scalars(select(model).where(*filters)).first()
        numeric, text = self._split_value(metric)
        if row is None:
            kwargs = dict(
                steam_app_id=game.steam_app_id,
                metric=metric.metric,
                observed_at=metric.observed_at,
                source_name=metric.source_name,
                source_mode=metric.source_mode,
                confidence=metric.confidence,
                source_url=metric.source_url,
                value_numeric=numeric,
                value_text=text,
            )
            if signal_type == "streaming":
                kwargs.update(external_game_id=game.twitch_lookup, game_name=game.name)
            self.session.add(model(**kwargs))
        else:
            row.value_numeric = numeric
            row.value_text = text
            row.source_mode = metric.source_mode
            row.confidence = metric.confidence
            row.source_url = metric.source_url

    def _persist_steamspy(self, game: GameIdentity, metrics: list[ProviderMetric]) -> None:
        if not metrics:
            return
        by_identity: dict[tuple[datetime, str], dict[str, ProviderMetric]] = {}
        for metric in metrics:
            by_identity.setdefault((metric.observed_at, metric.source_name), {})[metric.metric] = metric
        for (observed_at, source_name), group in by_identity.items():
            low_metric = group.get("owners_low_estimate")
            high_metric = group.get("owners_high_estimate")
            exemplar = low_metric or high_metric
            if exemplar is None:
                continue
            row = self.session.scalars(
                select(SteamSpySnapshotModel).where(
                    SteamSpySnapshotModel.steam_app_id == game.steam_app_id,
                    SteamSpySnapshotModel.observed_at == observed_at,
                    SteamSpySnapshotModel.source_name == source_name,
                )
            ).first()
            if row is None:
                row = SteamSpySnapshotModel(
                    steam_app_id=game.steam_app_id,
                    observed_at=observed_at,
                    source_name=source_name,
                    source_mode=exemplar.source_mode,
                    confidence=exemplar.confidence,
                    source_url=exemplar.source_url,
                )
                self.session.add(row)
            row.owners_low = int(low_metric.value) if low_metric and low_metric.value is not None else row.owners_low
            row.owners_high = int(high_metric.value) if high_metric and high_metric.value is not None else row.owners_high
            row.source_mode = exemplar.source_mode
            row.confidence = exemplar.confidence
            row.source_url = exemplar.source_url

    def _persist_reviews(self, game: GameIdentity, excerpts: list[ReviewExcerpt]) -> None:
        for excerpt in excerpts:
            row = self.session.get(ReviewModel, excerpt.review_id)
            values = {
                "steam_app_id": game.steam_app_id,
                "review_text": excerpt.text,
                "recommended": excerpt.recommended,
                "helpful_votes": excerpt.helpful_votes,
                "funny_votes": excerpt.funny_votes,
                "created_at_unix": excerpt.created_at_unix,
                "source_game_name": game.name,
                "source_name": excerpt.source_name,
                "source_mode": excerpt.source_mode,
                "source_url": excerpt.source_url,
            }
            if row is None:
                self.session.add(ReviewModel(review_id=excerpt.review_id, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)

    def refresh_catalog(self, limit: int | None = None) -> RefreshReport:
        games = self._games(limit)
        results: list[ProviderRunResult] = []
        total_metrics = 0

        for provider in self.providers:
            started_at = self.clock()
            written = 0
            errors: list[str] = []
            signal_type = str(getattr(provider, "signal_type", "")).strip().casefold()
            if signal_type not in {"steam", "streaming", "steamspy"}:
                errors.append(f"unsupported signal_type: {signal_type or 'missing'}")
            else:
                for record in games:
                    game = GameIdentity(record.steam_app_id, record.name, release_date=record.release_date)
                    try:
                        metrics = list(provider.fetch(game))
                        if signal_type == "steamspy":
                            self._persist_steamspy(game, metrics)
                        else:
                            for metric in metrics:
                                self._persist_regular(signal_type, game, metric)
                        written += len(metrics)
                    except Exception as exc:
                        errors.append(f"{record.steam_app_id}: {exc}")

            if written and errors:
                status = "partial"
            elif written:
                status = "success"
            else:
                status = "failure" if errors else "success"
            finished_at = self.clock()
            error_text = "; ".join(errors[:20]) if errors else None
            self.session.add(
                ProviderRunModel(
                    provider_name=str(getattr(provider, "provider_name", provider.__class__.__name__)),
                    started_at=started_at,
                    finished_at=finished_at,
                    status=status,
                    error_text=error_text,
                    metrics_written=written,
                )
            )
            self.session.commit()
            result = ProviderRunResult(
                provider_name=str(getattr(provider, "provider_name", provider.__class__.__name__)),
                status=status,
                metrics_written=written,
                error=error_text,
            )
            results.append(result)
            total_metrics += written

        has_failure = any(item.status != "success" for item in results)
        if total_metrics == 0 and has_failure:
            overall = "failure"
        elif has_failure:
            overall = "partial_success"
        else:
            overall = "success"
        return RefreshReport(overall, len(games), total_metrics, tuple(results))

    def refresh_game(self, app_id: int) -> RefreshReport:
        """Refresh one selected game without broadening into a catalog scan."""
        record = GameRepository(self.session).get_game(app_id)
        if record is None:
            return RefreshReport("failure", 0, 0, ())

        results: list[ProviderRunResult] = []
        total_metrics = 0
        game = GameIdentity(record.steam_app_id, record.name, release_date=record.release_date)
        for provider in self.providers:
            started_at = self.clock()
            written = 0
            error: str | None = None
            signal_type = str(getattr(provider, "signal_type", "")).strip().casefold()
            try:
                if signal_type not in {"steam", "streaming", "steamspy"}:
                    raise ValueError(f"unsupported signal_type: {signal_type or 'missing'}")
                metrics = list(provider.fetch(game))
                if signal_type == "steamspy":
                    self._persist_steamspy(game, metrics)
                else:
                    for metric in metrics:
                        self._persist_regular(signal_type, game, metric)
                written = len(metrics)
                review_fetcher = getattr(provider, "fetch_reviews", None)
                if callable(review_fetcher):
                    excerpts = list(review_fetcher(game))
                    self._persist_reviews(game, excerpts)
                    written += len(excerpts)
            except Exception as exc:
                error = str(exc)

            status = "partial" if written and error else "success" if written else "failure" if error else "success"
            self.session.add(
                ProviderRunModel(
                    provider_name=str(getattr(provider, "provider_name", provider.__class__.__name__)),
                    started_at=started_at,
                    finished_at=self.clock(),
                    status=status,
                    error_text=error,
                    metrics_written=written,
                )
            )
            self.session.commit()
            results.append(
                ProviderRunResult(
                    provider_name=str(getattr(provider, "provider_name", provider.__class__.__name__)),
                    status=status,
                    metrics_written=written,
                    error=error,
                )
            )
            total_metrics += written

        overall = "success" if results and all(item.status == "success" for item in results) else "partial_success" if total_metrics else "failure"
        return RefreshReport(overall, 1, total_metrics, tuple(results))

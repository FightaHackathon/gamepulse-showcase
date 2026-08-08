from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import os
import re
from collections.abc import Callable, Iterable
from typing import Any
import urllib.parse

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from gamepulse.db.connection import database_url as configured_database_url
from gamepulse.db.models import (
    GameGenreModel,
    GameModel,
    GameTagModel,
    ProviderRunModel,
    ReviewSummaryModel,
    SteamSnapshotModel,
    SteamSpySnapshotModel,
    StreamingSnapshotModel,
    TrendScoreModel,
)
from gamepulse.db.session import make_engine
from gamepulse.providers.contracts import GameIdentity, ProviderMetric
from gamepulse.providers.steam_public import SteamCurrentPlayersProvider
from gamepulse.providers.steamspy import SteamSpyProvider
from gamepulse.providers.twitchtracker import TwitchTrackerProvider


JsonFetcher = Callable[[str, float], object]
DEFAULT_APP_IDS = (620, 413150, 105600, 1145360, 1086940)
STEAM_STORE_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
STEAM_STORE_REVIEWS_URL = "https://store.steampowered.com/appreviews/{app_id}"


def _default_fetch_json(url: str, timeout: float) -> object:
    response = httpx.get(
        url,
        timeout=timeout,
        headers={"Accept": "application/json", "User-Agent": "GamePulse/1.0"},
    )
    response.raise_for_status()
    return response.json()


def _safe_error(error: object, database_url: str | None = None) -> str:
    text = str(error).strip() or error.__class__.__name__
    if database_url:
        text = text.replace(database_url, "[DATABASE_URL]")
    text = re.sub(r"(?i)(password|token|secret|api[_-]?key)=([^&\s]+)", r"\1=[REDACTED]", text)
    return text[:500]


def _observed_at(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _as_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _appdetails_url(app_id: int) -> str:
    query = urllib.parse.urlencode({"appids": int(app_id), "cc": "us", "l": "en"})
    return f"{STEAM_STORE_APPDETAILS_URL}?{query}"


def _review_url(app_id: int) -> str:
    query = urllib.parse.urlencode({"json": 1, "language": "all", "purchase_type": "all"})
    return f"{STEAM_STORE_REVIEWS_URL.format(app_id=int(app_id))}?{query}"


def _extract_appdetails(payload: object, app_id: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Steam Store appdetails response was not an object")
    item = payload.get(str(app_id), payload.get(app_id))
    if not isinstance(item, dict) or item.get("success") is False:
        raise ValueError("Steam Store appdetails did not contain a usable game")
    data = item.get("data", item)
    if not isinstance(data, dict) or not str(data.get("name", "")).strip():
        raise ValueError("Steam Store appdetails did not contain a game name")
    return data


def _catalog_row(app_id: int, data: dict[str, Any]) -> dict[str, object]:
    price = data.get("price_overview") or {}
    platforms = data.get("platforms") or {}
    release = data.get("release_date") or {}
    recommendations = data.get("recommendations") or {}
    metacritic = data.get("metacritic") or {}
    is_free = bool(data.get("is_free"))
    return {
        "steam_app_id": int(app_id),
        "name": str(data["name"]).strip(),
        "release_date": str(release.get("date") or "").strip() or None,
        "price_usd": 0.0 if is_free else (_as_float(price.get("final")) or 0.0) / 100.0 if price else None,
        "discount_pct": _as_float(price.get("discount_percent")) if price else None,
        "required_age": _as_int(data.get("required_age")),
        "recommendations": _as_int(recommendations.get("total")),
        "windows": bool(platforms.get("windows")) if "windows" in platforms else None,
        "mac": bool(platforms.get("mac")) if "mac" in platforms else None,
        "linux": bool(platforms.get("linux")) if "linux" in platforms else None,
        "metacritic_score": _as_float(metacritic.get("score")),
        "header_image_url": str(data.get("header_image") or "").strip() or None,
        "website_url": str(data.get("website") or "").strip() or None,
        "short_description": str(data.get("short_description") or "").strip() or None,
    }


def _values(data: object, key: str) -> tuple[str, ...]:
    if not isinstance(data, list):
        return ()
    output = {str(item.get(key, "")).strip() for item in data if isinstance(item, dict)}
    return tuple(sorted((item for item in output if item), key=str.casefold))


def _steamspy_tags(payload: object, app_id: int) -> tuple[str, ...] | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get(str(app_id), payload)
    if not isinstance(data, dict) or "tags" not in data:
        return None
    tags = data.get("tags")
    if not isinstance(tags, dict):
        return ()
    return tuple(sorted((str(tag).strip() for tag in tags if str(tag).strip()), key=str.casefold))


def _upsert_catalog(session: Session, row: dict[str, object], genres: tuple[str, ...], tags: tuple[str, ...] | None) -> None:
    app_id = int(row["steam_app_id"])
    game = session.get(GameModel, app_id)
    if game is None:
        game = GameModel(steam_app_id=app_id, name=str(row["name"]))
        session.add(game)
    for field, value in row.items():
        if field != "steam_app_id":
            setattr(game, field, value)
    session.flush()
    session.execute(delete(GameGenreModel).where(GameGenreModel.steam_app_id == app_id))
    for value in genres:
        session.add(GameGenreModel(steam_app_id=app_id, value=value))
    if tags is not None:
        session.execute(delete(GameTagModel).where(GameTagModel.steam_app_id == app_id))
        for value in tags:
            session.add(GameTagModel(steam_app_id=app_id, value=value))
    session.commit()


def _upsert_review(session: Session, app_id: int, summary: dict[str, object]) -> None:
    row = session.get(ReviewSummaryModel, app_id)
    if row is None:
        row = ReviewSummaryModel(steam_app_id=app_id)
        session.add(row)
    for field, value in summary.items():
        setattr(row, field, value)
    session.commit()


def _review_summary(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("Steam review response was not an object")
    summary = payload.get("query_summary")
    if not isinstance(summary, dict):
        raise ValueError("Steam review response did not contain a summary")
    result = {
        "review_count": _as_int(summary.get("total_reviews")) or _as_int(summary.get("num_reviews")) or 0,
        "recommended_count": _as_int(summary.get("total_positive")) or 0,
        "not_recommended_count": _as_int(summary.get("total_negative")) or 0,
    }
    review_score = _as_float(summary.get("review_score"))
    # Steam's review endpoint reports a 0–10 score; GamePulse stores the
    # normalized 0–1 fraction used by the existing API and UI.
    result["review_score"] = review_score / 10.0 if review_score is not None and review_score > 1 else review_score
    return result


def _record_provider_run(
    session: Session,
    provider_name: str,
    status: str,
    observed_at: datetime,
    metrics_written: int,
    errors: Iterable[str] = (),
) -> None:
    error_text = "; ".join(str(item)[:500] for item in list(errors)[:20]) or None
    session.add(
        ProviderRunModel(
            provider_name=provider_name,
            started_at=observed_at,
            finished_at=observed_at,
            status=status,
            error_text=error_text,
            metrics_written=int(metrics_written),
        )
    )
    session.commit()


def _split_metric(metric: ProviderMetric) -> tuple[float | None, str | None]:
    value = metric.value
    if value is None:
        return None, None
    if isinstance(value, bool):
        return float(value), None
    if isinstance(value, (int, float)):
        return float(value), None
    return None, str(value)


def _persist_metric(session: Session, game: GameIdentity, metric: ProviderMetric, signal_type: str) -> None:
    numeric, text = _split_metric(metric)
    if signal_type == "steam":
        model = SteamSnapshotModel
    elif signal_type == "streaming":
        model = StreamingSnapshotModel
    else:
        raise ValueError(f"unsupported signal type: {signal_type}")
    row = session.scalars(
        select(model).where(
            model.steam_app_id == game.steam_app_id,
            model.metric == metric.metric,
            model.observed_at == metric.observed_at,
            model.source_name == metric.source_name,
        )
    ).first()
    values = {
        "value_numeric": numeric,
        "value_text": text,
        "source_mode": metric.source_mode,
        "confidence": metric.confidence,
        "source_url": metric.source_url,
    }
    if row is None:
        values.update(steam_app_id=game.steam_app_id, metric=metric.metric, observed_at=metric.observed_at, source_name=metric.source_name)
        if signal_type == "streaming":
            values.update(external_game_id=game.twitch_lookup, game_name=game.name)
        session.add(model(**values))
    else:
        for key, value in values.items():
            setattr(row, key, value)


def _persist_steamspy(session: Session, game: GameIdentity, metrics: list[ProviderMetric]) -> None:
    if not metrics:
        return
    exemplar = metrics[0]
    row = session.scalars(
        select(SteamSpySnapshotModel).where(
            SteamSpySnapshotModel.steam_app_id == game.steam_app_id,
            SteamSpySnapshotModel.observed_at == exemplar.observed_at,
            SteamSpySnapshotModel.source_name == exemplar.source_name,
        )
    ).first()
    if row is None:
        row = SteamSpySnapshotModel(
            steam_app_id=game.steam_app_id,
            observed_at=exemplar.observed_at,
            source_name=exemplar.source_name,
            source_mode=exemplar.source_mode,
            confidence=exemplar.confidence,
            source_url=exemplar.source_url,
        )
        session.add(row)
    for metric in metrics:
        if metric.metric == "owners_low_estimate":
            row.owners_low = _as_int(metric.value)
        elif metric.metric == "owners_high_estimate":
            row.owners_high = _as_int(metric.value)
    row.source_mode = exemplar.source_mode
    row.confidence = exemplar.confidence
    row.source_url = exemplar.source_url


def _refresh_provider(
    session: Session,
    games: list[GameIdentity],
    provider: object,
    observed_at: datetime,
    database_url: str,
) -> tuple[str, int, str | None]:
    provider_name = str(getattr(provider, "provider_name", provider.__class__.__name__))
    signal_type = str(getattr(provider, "signal_type", "")).casefold()
    errors: list[str] = []
    written = 0
    if signal_type not in {"steam", "streaming", "steamspy"}:
        errors.append(f"unsupported signal_type: {signal_type or 'missing'}")
    else:
        for game in games:
            try:
                metrics = list(provider.fetch(game))  # type: ignore[attr-defined]
                if signal_type == "steamspy":
                    _persist_steamspy(session, game, metrics)
                else:
                    for metric in metrics:
                        _persist_metric(session, game, metric, signal_type)
                session.commit()
                written += len(metrics)
            except Exception as exc:
                session.rollback()
                errors.append(f"{game.steam_app_id}: {_safe_error(exc, database_url)}")
    status = "partial" if written and errors else "success" if written or not errors else "failure"
    _record_provider_run(session, provider_name, status, observed_at, written, errors)
    return status, written, "; ".join(errors[:20]) if errors else None


def _bounded_score(value: float, denominator: float) -> float:
    if value <= 0:
        return 0.0
    return round(max(0.0, min(100.0, 100.0 * math.log1p(value) / math.log1p(denominator))), 4)


def _upsert_trends(session: Session, app_ids: list[int], observed_at: datetime) -> int:
    written = 0
    for app_id in app_ids:
        game = session.get(GameModel, app_id)
        if game is None:
            continue
        current_players = session.scalars(
            select(SteamSnapshotModel.value_numeric).where(
                SteamSnapshotModel.steam_app_id == app_id,
                SteamSnapshotModel.metric == "current_players",
                SteamSnapshotModel.observed_at == observed_at,
            )
        ).first()
        streaming_values = dict(
            session.execute(
                select(StreamingSnapshotModel.metric, StreamingSnapshotModel.value_numeric).where(
                    StreamingSnapshotModel.steam_app_id == app_id,
                    StreamingSnapshotModel.observed_at == observed_at,
                )
            ).all()
        )
        player_score = _bounded_score(float(current_players or 0), 1_000_000)
        streamer_score = round(
            max(
                0.0,
                min(
                    100.0,
                    0.6 * _bounded_score(float(streaming_values.get("hours_watched_30d") or 0), 100_000)
                    + 0.4 * _bounded_score(float(streaming_values.get("average_viewers_30d") or 0), 100_000),
                ),
            ),
            4,
        )
        review_score = float(game.review_score or 0)
        review_component = max(0.0, min(100.0, review_score * 10.0))
        developer_score = round(
            max(0.0, min(100.0, 0.55 * _bounded_score(float(game.total_reviews or 0), 1_000_000) + 0.45 * review_component)),
            4,
        )
        values = {
            "player": (player_score, {"current_players": current_players or 0}),
            "streamer": (
                streamer_score,
                {
                    "hours_watched_30d": streaming_values.get("hours_watched_30d") or 0,
                    "average_viewers_30d": streaming_values.get("average_viewers_30d") or 0,
                },
            ),
            "developer": (
                developer_score,
                {"total_reviews": game.total_reviews or 0, "review_score": review_score},
            ),
        }
        for audience, (score, components) in values.items():
            row = session.scalars(
                select(TrendScoreModel).where(
                    TrendScoreModel.steam_app_id == app_id,
                    TrendScoreModel.audience == audience,
                    TrendScoreModel.observed_at == observed_at,
                )
            ).first()
            if row is None:
                row = TrendScoreModel(
                    steam_app_id=app_id,
                    audience=audience,
                    observed_at=observed_at,
                    source_name="GamePulse Bootstrap",
                    source_mode="derived",
                    confidence="medium",
                )
                session.add(row)
                written += 1
            row.score = score
            row.components = components
        session.commit()
    return written


@dataclass(frozen=True)
class BootstrapReport:
    status: str
    games_requested: int
    catalog_succeeded: int
    catalog_failed: int
    reviews_succeeded: int
    metrics_written: int
    trends_written: int
    errors: tuple[str, ...]

    @property
    def catalog_failed_count(self) -> int:
        return self.catalog_failed

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_bootstrap(
    database_url: str,
    *,
    app_ids: Iterable[int] | None = None,
    limit: int | None = None,
    observed_at: datetime | str | None = None,
    timeout_seconds: float = 15.0,
    fetch_json: JsonFetcher | None = None,
) -> BootstrapReport:
    if timeout_seconds <= 0:
        raise ValueError("timeout must be greater than zero")
    requested = list(app_ids if app_ids is not None else DEFAULT_APP_IDS)
    normalized: list[int] = []
    for app_id in requested:
        value = _as_int(app_id)
        if value is None or value <= 0:
            raise ValueError("app IDs must be positive integers")
        if value not in normalized:
            normalized.append(value)
    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        normalized = normalized[: int(limit)]
    observed = _observed_at(observed_at)
    effective_fetch_json = fetch_json or _default_fetch_json
    steamspy_payloads: dict[int, object] = {}

    def steamspy_fetch(url: str, timeout: float) -> object:
        payload = effective_fetch_json(url, timeout)
        match = re.search(r"appid=(\d+)", url)
        if match:
            steamspy_payloads[int(match.group(1))] = payload
        return payload

    steam_provider = SteamCurrentPlayersProvider(
        fetch_json=effective_fetch_json,
        timeout_seconds=timeout_seconds,
        clock=lambda: observed,
    )
    steamspy_provider = SteamSpyProvider(
        fetch_json=steamspy_fetch,
        timeout_seconds=timeout_seconds,
        clock=lambda: observed,
    )
    twitch_provider = TwitchTrackerProvider(
        fetch_json=effective_fetch_json,
        timeout_seconds=timeout_seconds,
        clock=lambda: observed,
    )

    engine = make_engine(configured_database_url(database_url))
    catalog_errors: list[str] = []
    review_errors: list[str] = []
    refresh_errors: list[str] = []
    successful_ids: list[int] = []
    review_successes = 0
    metrics_written = 0
    trends_written = 0
    try:
        with Session(engine) as session:
            catalog_metrics = 0
            for app_id in normalized:
                try:
                    data = _extract_appdetails(effective_fetch_json(_appdetails_url(app_id), timeout_seconds), app_id)
                    row = _catalog_row(app_id, data)
                    tags = _steamspy_tags(steamspy_payloads.get(app_id), app_id)
                    _upsert_catalog(session, row, _values(data.get("genres"), "description"), tags)
                    successful_ids.append(app_id)
                    catalog_metrics += 1
                except Exception as exc:
                    session.rollback()
                    catalog_errors.append(f"{app_id}: {_safe_error(exc, database_url)}")
            catalog_status = "partial" if catalog_metrics and catalog_errors else "success" if catalog_metrics else "failure"
            _record_provider_run(session, "Steam Store Catalog", catalog_status, observed, catalog_metrics, catalog_errors)

            for app_id in successful_ids:
                try:
                    summary = _review_summary(effective_fetch_json(_review_url(app_id), timeout_seconds))
                    _upsert_review(session, app_id, summary)
                    game = session.get(GameModel, app_id)
                    if game is not None:
                        game.positive_reviews = summary["recommended_count"]
                        game.negative_reviews = summary["not_recommended_count"]
                        game.total_reviews = summary["review_count"]
                        game.review_score = summary["review_score"]
                        session.commit()
                    review_successes += 1
                except Exception as exc:
                    session.rollback()
                    review_errors.append(f"{app_id}: {_safe_error(exc, database_url)}")
            review_status = "partial" if review_successes and review_errors else "success" if review_successes else "failure" if successful_ids else "failure"
            _record_provider_run(session, "Steam Reviews API", review_status, observed, review_successes, review_errors or (("no catalog games available",) if not successful_ids else ()))

            games = [
                GameIdentity(app_id, session.get(GameModel, app_id).name, release_date=session.get(GameModel, app_id).release_date)
                for app_id in successful_ids
                if session.get(GameModel, app_id) is not None
            ]
            for provider in (steam_provider, twitch_provider, steamspy_provider):
                status, written, error = _refresh_provider(session, games, provider, observed, database_url)
                metrics_written += written
                if error:
                    refresh_errors.append(f"{getattr(provider, 'provider_name', provider.__class__.__name__)}: {error}")

            # Steam Store appdetails exposes genres but not the community tags
            # used by the existing catalog UI.  Reuse the successful SteamSpy
            # response captured by the provider adapter when it is available.
            for app_id in successful_ids:
                tags = _steamspy_tags(steamspy_payloads.get(app_id), app_id)
                if tags is None:
                    continue
                session.execute(delete(GameTagModel).where(GameTagModel.steam_app_id == app_id))
                for value in tags:
                    session.add(GameTagModel(steam_app_id=app_id, value=value))
                session.commit()

            trends_written = _upsert_trends(session, successful_ids, observed)
    finally:
        engine.dispose()

    errors = tuple((catalog_errors + review_errors + refresh_errors)[:20])
    if not successful_ids:
        status = "failure"
    elif errors:
        status = "partial_success"
    else:
        status = "success"
    return BootstrapReport(
        status=status,
        games_requested=len(normalized),
        catalog_succeeded=len(successful_ids),
        catalog_failed=len(catalog_errors),
        reviews_succeeded=review_successes,
        metrics_written=metrics_written,
        trends_written=trends_written,
        errors=errors,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed a bounded real Steam catalog into the existing GamePulse database.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"), help="SQLAlchemy DATABASE_URL (or DATABASE_URL environment variable).")
    parser.add_argument("--app-id", action="append", type=int, dest="app_ids", help="Steam app ID; may be repeated. Defaults to a deterministic curated list.")
    parser.add_argument("--limit", type=int, help="Maximum number of app IDs to seed.")
    parser.add_argument("--observed-at", help="Fixed ISO-8601 observation timestamp; naive values are treated as UTC.")
    parser.add_argument("--timeout", "--timeout-seconds", type=float, default=15.0, dest="timeout_seconds", help="Provider request timeout in seconds.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if not args.database_url:
            raise ValueError("DATABASE_URL is required")
        report = run_bootstrap(
            args.database_url,
            app_ids=args.app_ids,
            limit=args.limit,
            observed_at=args.observed_at,
            timeout_seconds=args.timeout_seconds,
        )
        print(json.dumps(report.to_dict(), sort_keys=True))
        return 0 if report.status == "success" else 1
    except Exception as exc:
        print(json.dumps({"status": "failure", "error": _safe_error(exc, args.database_url)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

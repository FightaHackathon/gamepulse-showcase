from __future__ import annotations

from datetime import datetime, timezone
import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gamepulse.db.models import (
    Base,
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
from gamepulse.jobs.bootstrap_catalog import run_bootstrap


OBSERVED_AT = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)


def _payloads(*, fail_app_id: int | None = None, fail_twitch_app_id: int | None = None):
    def fetch_json(url: str, timeout: float):
        if fail_app_id is not None and f"appids={fail_app_id}" in url:
            raise RuntimeError("catalog upstream unavailable")
        if "/appreviews/" in url:
            return {
                "query_summary": {
                    "num_reviews": 120,
                    "total_reviews": 240,
                    "total_positive": 100,
                    "total_negative": 20,
                    "review_score": 8,
                }
            }
        if "GetNumberOfCurrentPlayers" in url:
            return {"response": {"result": 1, "player_count": 500}}
        if "steamspy.com" in url:
            return {"appid": 10, "owners": "1,000 .. 2,000", "tags": {"RPG": 10, "Indie": 4}}
        if "twitchtracker.com" in url:
            if fail_twitch_app_id is not None and "Example%20Game" in url:
                raise RuntimeError("streaming upstream unavailable")
            return {"data": {"hours_watched": 100, "avg_viewers": 250, "avg_channels": 5, "rank": 12}}
        return {
            "10": {
                "success": True,
                "data": {
                    "name": "Example Game",
                    "release_date": {"date": "2024-01-02"},
                    "is_free": False,
                    "price_overview": {"final": 1999, "discount_percent": 10},
                    "required_age": "12",
                    "platforms": {"windows": True, "mac": False, "linux": True},
                    "genres": [{"description": "RPG"}],
                    "recommendations": {"total": 300},
                    "metacritic": {"score": 90},
                    "header_image": "https://cdn.example/header.jpg",
                    "website": "https://example.test",
                    "short_description": "A useful fixture.",
                },
            }
        }

    return fetch_json


def _database_url(tmp_path):
    return f"sqlite+pysqlite:///{tmp_path / 'bootstrap.sqlite3'}"


def _create_schema(tmp_path):
    engine = create_engine(_database_url(tmp_path))
    Base.metadata.create_all(engine)
    engine.dispose()


def test_bootstrap_persists_provenance_trends_and_is_idempotent(tmp_path):
    _create_schema(tmp_path)
    database_url = _database_url(tmp_path)
    first = run_bootstrap(
        database_url,
        app_ids=[10],
        observed_at=OBSERVED_AT,
        fetch_json=_payloads(),
    )
    second = run_bootstrap(
        database_url,
        app_ids=[10],
        observed_at=OBSERVED_AT,
        fetch_json=_payloads(),
    )

    assert first.status == second.status == "success"
    engine = create_engine(database_url)
    with Session(engine) as session:
        assert session.scalars(select(GameModel)).all()[0].name == "Example Game"
        assert [row.value for row in session.scalars(select(GameTagModel)).all()] == ["Indie", "RPG"]
        assert [row.value for row in session.scalars(select(GameGenreModel)).all()] == ["RPG"]
        review = session.get(ReviewSummaryModel, 10)
        assert review is not None
        assert (review.review_count, review.recommended_count, review.not_recommended_count) == (240, 100, 20)
        assert review.review_score == 0.8

        steam = session.scalars(select(SteamSnapshotModel)).all()
        streaming = session.scalars(select(StreamingSnapshotModel)).all()
        steamspy = session.scalars(select(SteamSpySnapshotModel)).all()
        assert len(steam) == 1
        assert len(streaming) == 5
        assert len(steamspy) == 1
        assert steam[0].observed_at.replace(tzinfo=timezone.utc) == OBSERVED_AT
        assert steamspy[0].source_mode == "public_estimate"
        assert steamspy[0].confidence == "low"
        assert steamspy[0].owners_low == 1000
        assert len(session.scalars(select(TrendScoreModel)).all()) == 3
        scores = session.scalars(select(TrendScoreModel)).all()
        assert {row.audience for row in scores} == {"player", "streamer", "developer"}
        assert all(0 <= row.score <= 100 for row in scores)
    engine.dispose()


def test_bootstrap_isolates_catalog_and_provider_failures(tmp_path):
    _create_schema(tmp_path)
    report = run_bootstrap(
        _database_url(tmp_path),
        app_ids=[10, 20],
        observed_at=OBSERVED_AT,
        fetch_json=_payloads(fail_app_id=20, fail_twitch_app_id=10),
    )

    assert report.status == "partial_success"
    assert report.catalog_failed == 1
    engine = create_engine(_database_url(tmp_path))
    with Session(engine) as session:
        assert session.get(GameModel, 10) is not None
        assert session.get(GameModel, 20) is None
        runs = session.scalars(select(ProviderRunModel).order_by(ProviderRunModel.id)).all()
        assert any(row.provider_name == "Steam Store Catalog" and row.status == "partial" for row in runs)
        assert any(row.provider_name == "TwitchTracker" and row.status == "failure" for row in runs)
        assert session.scalars(select(TrendScoreModel)).all()
        assert all("DATABASE_URL" not in (row.error_text or "") for row in runs)
    engine.dispose()


def test_bootstrap_report_is_json_serializable(tmp_path):
    _create_schema(tmp_path)
    report = run_bootstrap(
        _database_url(tmp_path),
        app_ids=[10],
        observed_at=OBSERVED_AT,
        fetch_json=_payloads(),
    )
    json.dumps(report.to_dict())

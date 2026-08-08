from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gamepulse.db.models import (
    Base,
    GameModel,
    ProviderRunModel,
    SteamSnapshotModel,
    SteamSpySnapshotModel,
    StreamingSnapshotModel,
)
from gamepulse.providers.contracts import ProviderError, ProviderMetric
from gamepulse.services.snapshot_refresh import SnapshotRefreshService


NOW = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)


class SteamProvider:
    provider_name = "Steam Web API"
    signal_type = "steam"

    def fetch(self, game):
        return [
            ProviderMetric(
                metric="current_players",
                value=1234,
                observed_at=NOW,
                source_name=self.provider_name,
                source_mode="public_api",
                confidence="high",
            )
        ]


class FailingStreamingProvider:
    provider_name = "TwitchTracker"
    signal_type = "streaming"

    def fetch(self, game):
        raise ProviderError("temporary upstream failure")


class SteamSpyProvider:
    provider_name = "SteamSpy"
    signal_type = "steamspy"

    def fetch(self, game):
        common = dict(
            observed_at=NOW,
            source_name=self.provider_name,
            source_mode="public_estimate",
            confidence="low",
        )
        return [
            ProviderMetric(metric="owners_low_estimate", value=100_000, **common),
            ProviderMetric(metric="owners_high_estimate", value=200_000, **common),
        ]


def test_refresh_persists_successes_and_records_provider_failure():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(GameModel(steam_app_id=10, name="Example Game"))
        session.commit()

        report = SnapshotRefreshService(
            session,
            [SteamProvider(), FailingStreamingProvider(), SteamSpyProvider()],
            clock=lambda: NOW,
        ).refresh_catalog()

        assert report.status == "partial_success"
        assert report.games_considered == 1
        assert report.metrics_written == 3

        steam_rows = session.scalars(select(SteamSnapshotModel)).all()
        assert len(steam_rows) == 1
        assert steam_rows[0].metric == "current_players"
        assert steam_rows[0].value_numeric == 1234

        assert session.scalars(select(StreamingSnapshotModel)).all() == []

        steamspy_rows = session.scalars(select(SteamSpySnapshotModel)).all()
        assert len(steamspy_rows) == 1
        assert steamspy_rows[0].owners_low == 100_000
        assert steamspy_rows[0].owners_high == 200_000

        runs = session.scalars(select(ProviderRunModel).order_by(ProviderRunModel.id)).all()
        assert [(row.provider_name, row.status) for row in runs] == [
            ("Steam Web API", "success"),
            ("TwitchTracker", "failure"),
            ("SteamSpy", "success"),
        ]
        assert "temporary upstream failure" in (runs[1].error_text or "")

    engine.dispose()

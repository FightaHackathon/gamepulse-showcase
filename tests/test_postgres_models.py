import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gamepulse.db.models import Base, GameModel, SteamSnapshotModel, StreamingSnapshotModel


TEST_DATABASE_URL = os.getenv("GAMEPULSE_TEST_DATABASE_URL")


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="GAMEPULSE_TEST_DATABASE_URL is not configured")
def test_postgres_schema_stores_provenance_for_steam_and_streaming_metrics():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    observed = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)
    try:
        with Session(engine) as session:
            session.merge(GameModel(steam_app_id=10, name="Counter-Strike"))
            session.add(
                SteamSnapshotModel(
                    steam_app_id=10,
                    metric="current_players",
                    value_numeric=1234,
                    value_text=None,
                    observed_at=observed,
                    source_name="Steam",
                    source_mode="public_api",
                    confidence="high",
                    source_url="https://api.steampowered.com/",
                )
            )
            session.add(
                StreamingSnapshotModel(
                    steam_app_id=10,
                    external_game_id="Counter-Strike",
                    game_name="Counter-Strike",
                    metric="average_viewers_30d",
                    value_numeric=999,
                    value_text=None,
                    observed_at=observed,
                    source_name="TwitchTracker",
                    source_mode="public_summary",
                    confidence="medium",
                    source_url="https://twitchtracker.com/api",
                )
            )
            session.commit()
            steam = session.scalars(select(SteamSnapshotModel).where(SteamSnapshotModel.steam_app_id == 10)).first()
            streaming = session.scalars(select(StreamingSnapshotModel).where(StreamingSnapshotModel.steam_app_id == 10)).first()
            assert steam is not None and steam.source_name == "Steam" and steam.confidence == "high"
            assert streaming is not None and streaming.source_name == "TwitchTracker" and streaming.confidence == "medium"
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()

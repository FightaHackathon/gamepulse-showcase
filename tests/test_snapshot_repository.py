from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from gamepulse.db.models import Base, GameModel, GameTagModel
from gamepulse.db.repositories import GameRepository, GameSignalSnapshot, SnapshotRepository


def make_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_game_repository_returns_typed_game_with_tags():
    session = make_session()
    session.add(GameModel(steam_app_id=10, name="Counter-Strike", header_image_url="https://example.test/10.jpg"))
    session.add(GameTagModel(steam_app_id=10, value="Action"))
    session.commit()

    game = GameRepository(session).get_game(10)

    assert game is not None
    assert game.steam_app_id == 10
    assert game.tags == ("Action",)


def test_snapshot_repository_upserts_and_returns_history():
    session = make_session()
    session.add(GameModel(steam_app_id=10, name="Counter-Strike"))
    session.commit()
    repository = SnapshotRepository(session)
    observed = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)
    snapshot = GameSignalSnapshot(
        steam_app_id=10,
        signal_type="steam",
        metric="current_players",
        value_numeric=1234,
        value_text=None,
        observed_at=observed,
        source_name="Steam",
        source_mode="public_api",
        confidence="high",
        source_url="https://api.steampowered.com/",
    )

    repository.upsert_snapshot(snapshot)
    repository.upsert_snapshot(snapshot)

    history = repository.history_for_game(10, "current_players", 10)
    assert len(history) == 1
    assert history[0].value_numeric == 1234
    assert repository.latest_for_game(10) == snapshot

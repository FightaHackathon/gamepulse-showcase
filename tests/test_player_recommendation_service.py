from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gamepulse.db.models import Base, GameGenreModel, GameModel, GameTagModel, SteamSnapshotModel
from gamepulse.providers.steam import PlayerLibrary
from gamepulse.services.player_recommendations import PlayerRecommendationService


NOW = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)


def add_game(session, app_id, name, tags, genres, review_score, players_now, players_before):
    session.add(
        GameModel(
            steam_app_id=app_id,
            name=name,
            review_score=review_score,
            total_reviews=1000,
            header_image_url=f"https://example.test/{app_id}.jpg",
        )
    )
    session.add_all(GameTagModel(steam_app_id=app_id, value=value) for value in tags)
    session.add_all(GameGenreModel(steam_app_id=app_id, value=value) for value in genres)
    for observed_at, value in (
        (NOW - timedelta(days=7), players_before),
        (NOW, players_now),
    ):
        session.add(
            SteamSnapshotModel(
                steam_app_id=app_id,
                metric="current_players",
                value_numeric=value,
                value_text=None,
                source_name="Steam Web API",
                source_mode="public_api",
                observed_at=observed_at,
                confidence="high",
                source_url=None,
            )
        )


def test_player_recommendations_keep_owned_and_discovery_mutually_exclusive():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_game(session, 1, "Owned Co-op", ["Co-op", "Shooter"], ["Action"], 0.90, 1200, 900)
        add_game(session, 2, "Owned Strategy", ["Strategy"], ["Strategy"], 0.82, 400, 500)
        add_game(session, 3, "Matching Discovery", ["Co-op", "Shooter"], ["Action"], 0.94, 1800, 1100)
        add_game(session, 4, "Popular Unrelated", ["Racing"], ["Racing"], 0.96, 20000, 19000)
        session.commit()

        library = PlayerLibrary(
            steam_id="76561198000000000",
            games=(
                {"appid": 1, "name": "Owned Co-op", "playtime_forever": 5000, "playtime_2weeks": 240},
                {"appid": 2, "name": "Owned Strategy", "playtime_forever": 150, "playtime_2weeks": 0},
            ),
            source_name="Steam Web API",
            complete=True,
        )

        owned, discovery = PlayerRecommendationService(session).recommend(library, limit_owned=10, limit_discovery=10)

        owned_ids = {item.app_id for item in owned}
        discovery_ids = {item.app_id for item in discovery}
        assert owned_ids <= {1, 2}
        assert discovery_ids.isdisjoint({1, 2})
        assert owned_ids.isdisjoint(discovery_ids)
        assert all(0 <= item.score <= 100 for item in [*owned, *discovery])
        assert all(item.owned for item in owned)
        assert all(not item.owned for item in discovery)

        matching = next(item for item in discovery if item.app_id == 3)
        unrelated = next(item for item in discovery if item.app_id == 4)
        assert matching.score > unrelated.score
        assert matching.breakdown.personal_fit > unrelated.breakdown.personal_fit
        assert matching.breakdown.review_quality is not None
        assert matching.breakdown.current_activity is not None
        assert matching.breakdown.trend_momentum is not None

    engine.dispose()


def test_missing_factor_is_renormalized_instead_of_scored_as_zero():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(GameModel(steam_app_id=10, name="Known Taste", review_score=1.0, total_reviews=100))
        session.add(GameTagModel(steam_app_id=10, value="Puzzle"))
        session.add(GameGenreModel(steam_app_id=10, value="Puzzle"))
        session.add(GameModel(steam_app_id=11, name="No Activity Candidate", review_score=1.0, total_reviews=100))
        session.add(GameTagModel(steam_app_id=11, value="Puzzle"))
        session.add(GameGenreModel(steam_app_id=11, value="Puzzle"))
        session.commit()

        library = PlayerLibrary(
            steam_id="76561198000000000",
            games=({"appid": 10, "playtime_forever": 3000, "playtime_2weeks": 0},),
            complete=True,
        )
        _, discovery = PlayerRecommendationService(session).recommend(library)
        result = next(item for item in discovery if item.app_id == 11)

        assert result.breakdown.current_activity is None
        assert result.breakdown.trend_momentum is None
        assert result.score >= 95

    engine.dispose()

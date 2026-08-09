from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from gamepulse.db.models import Base, GameGenreModel, GameModel, GameTagModel, SteamSnapshotModel
from gamepulse.providers.steam import PlayerLibrary
from gamepulse.services.player_recommendations import PlayerRecommendationService
from gamepulse.services import player_recommendations


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
        add_game(session, 3, "Matching Discovery", ["Co-op", "Shooter", "Fighting", "Video Production"], ["Action"], 0.94, 1800, 1100)
        add_game(session, 4, "Popular Unrelated", ["Racing"], ["Racing"], 0.96, 20000, 19000)
        add_game(session, 5, "Genre-only Discovery", [], ["Action"], None, None, None)
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
        assert next(item for item in discovery if item.app_id == 3).genres == ("Action",)
        assert next(item for item in discovery if item.app_id == 3).tags == ("Co-op", "Fighting", "Shooter")

        matching = next(item for item in discovery if item.app_id == 3)
        genre_only = next(item for item in discovery if item.app_id == 5)
        unrelated = next(item for item in discovery if item.app_id == 4)
        assert matching.score > unrelated.score
        assert genre_only.breakdown.personal_fit > 0.5
        assert genre_only.score < 100
        assert genre_only.score > unrelated.score
        assert "Owned Co-op" in " ".join(genre_only.reasons)
        assert "Action" in " ".join(genre_only.reasons)
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


def test_catalog_pages_prioritize_newest_neon_release_records():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            GameModel(steam_app_id=1, name="Older Neon Game", release_date="2018-01-01"),
            GameModel(steam_app_id=2, name="Newest Neon Game", release_date="2025-01-01"),
            GameModel(steam_app_id=3, name="Undated Neon Game", release_date=None),
        ])
        session.commit()

        catalog, _ = PlayerRecommendationService(session)._catalog(set(), limit=3)

        assert [game.app_id for game in catalog] == [2, 1, 3]

    engine.dispose()


def test_player_recommendations_surface_artifact_peak_ccu_for_multiple_catalog_games(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        add_game(session, 20, "Artifact One", ["Action"], ["Action"], 0.8, None, None)
        add_game(session, 21, "Artifact Two", ["Action"], ["Action"], 0.8, None, None)
        session.commit()

        monkeypatch.setattr(
            player_recommendations,
            "load_peak_ccu_artifact",
            lambda: {20: 2200, 21: 3300},
        )
        _, discovery = PlayerRecommendationService(session).recommend(
            PlayerLibrary(steam_id="test", games=()), limit_discovery=10
        )

        by_id = {item.app_id: item for item in discovery}
        assert by_id[20].current_players is None
        assert by_id[20].peak_ccu == 2200
        assert by_id[21].peak_ccu == 3300

    engine.dispose()


def test_player_recommendations_bound_catalog_queries_and_keep_owned_games():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for app_id in range(1, 106):
            add_game(session, app_id, f"Game {app_id:03d}", ["Action"], ["Action"], 0.8, 100 + app_id, 90 + app_id)
        session.commit()

    statements = []

    def count_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith(("SELECT", "WITH")):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", count_statement)
    try:
        with Session(engine) as session:
            library = PlayerLibrary(
                steam_id="76561198000000000",
                games=({"appid": 105, "playtime_forever": 1200, "playtime_2weeks": 0},),
                complete=True,
            )
            owned, discovery = PlayerRecommendationService(session).recommend(library)
    finally:
        event.remove(engine, "before_cursor_execute", count_statement)
        engine.dispose()

    assert [item.app_id for item in owned] == [105]
    assert discovery
    assert any("FROM games" in statement and "LIMIT" in statement.upper() for statement in statements)
    # Recent + popularity Neon slices remain set-based and bounded.
    assert len(statements) <= 8


def test_player_recommendations_page_four_bounded_catalog_windows_are_deduped_and_unowned():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for app_id in range(1, 401):
            session.add(GameModel(steam_app_id=app_id, name=f"Game {app_id:03d}", review_score=0.8))
            session.add(GameTagModel(steam_app_id=app_id, value="Action"))
            session.add(GameGenreModel(steam_app_id=app_id, value="Action"))
        session.commit()

        library = PlayerLibrary(
            steam_id="76561198000000000",
            games=({"appid": 150, "playtime_forever": 1200},),
            complete=True,
        )
        pages = []
        for page in range(4):
            owned, discovery, has_more = PlayerRecommendationService(session).recommend(
                library,
                limit_owned=10,
                limit_discovery=100,
                catalog_offset=page * 100,
                return_page_info=True,
            )
            assert len([*owned, *discovery]) <= 100
            assert len(discovery) <= 100
            assert all(not item.owned for item in discovery)
            assert has_more is (page < 3)
            pages.extend(item.app_id for item in discovery)

        assert len(pages) == 399
        assert len(set(pages)) == len(pages)
        assert 150 not in pages

    engine.dispose()

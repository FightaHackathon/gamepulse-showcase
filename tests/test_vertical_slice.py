import unittest
from pathlib import Path

from gamepulse.catalog import Catalog
from gamepulse.config import Settings
from gamepulse.forecasting import daily_counts_for_game, forecast_review_activity
from gamepulse.market_analysis import MarketSnapshot, analyze_developer_opportunity, analyze_market, latest_market_snapshot
from gamepulse.providers.twitch import TwitchProvider
from gamepulse.recommendations import PlayerPreferences, RecommendationEngine
from gamepulse.review_analysis import analyze_reviews
from gamepulse.streamer_fit import StreamerProfile as FitProfile, rank_streamers
from gamepulse.streamer_opportunity import (
    StreamerProfile as OpportunityProfile,
    find_matching_opportunity,
    score_game_opportunities,
)


ROOT = Path(__file__).resolve().parents[1]


class VerticalSliceAcceptanceTests(unittest.TestCase):
    def test_curated_game_supports_the_complete_three_user_story(self):
        settings = Settings.from_env(ROOT)
        catalog = Catalog(settings.database_path)
        game = catalog.rank_demo_candidates(1)[0]

        recommendations = RecommendationEngine(settings.database_path).recommend_similar(
            game.steam_app_id,
            PlayerPreferences(preferred_tags=game.tags[:2], preferred_genres=game.genres[:2]),
            limit=8,
        )
        self.assertTrue(recommendations, "Player Mode should have at least one recommendation")

        provider = TwitchProvider(settings.twitch_snapshot_path, settings.twitch_client_id, settings.twitch_client_secret)
        twitch_trends = provider.get_game_trends()
        opportunities = score_game_opportunities(twitch_trends.data, OpportunityProfile(channel_size_tier="emerging"))
        self.assertTrue(opportunities, "Streamer Mode should have a ranked opportunity list")
        selected_opportunity = find_matching_opportunity(opportunities, game.name)
        self.assertIsNotNone(selected_opportunity, "The selected game must have a matching Twitch category for the complete story")
        creator_snapshot = provider.get_streamers(selected_opportunity.game_id)
        fits = rank_streamers(
            {"name": game.name, "genres": set(game.genres), "tags": set(game.tags), "language": "en"},
            [
                FitProfile(item.streamer_id, set(item.tags) | {item.game_name}, item.language, item.channel_size_tier, item.viewer_count)
                for item in creator_snapshot.data
            ],
        )
        self.assertTrue(fits, "Developer Mode should have creator-fit evidence")

        comparables = catalog.comparable_games(game.steam_app_id, limit=5)
        self.assertTrue(comparables, "Developer Mode should have comparable games")
        review_analysis = analyze_reviews(settings.database_path, game.steam_app_id)
        self.assertGreater(review_analysis.review_count, 0)
        forecast = forecast_review_activity(daily_counts_for_game(settings.database_path, game.steam_app_id))
        self.assertLessEqual(forecast.low, forecast.expected)
        self.assertLessEqual(forecast.expected, forecast.high)

        snapshot = latest_market_snapshot(settings.database_path, game.steam_app_id) or MarketSnapshot(
            game.steam_app_id,
            None,
            game.owners_low,
            game.owners_high,
            game.price_usd,
            game.total_reviews,
            game.peak_ccu,
            "Local prepared data",
            "prepared fixture",
            "2026-08-01",
        )
        market = analyze_market(snapshot, [{"name": item.name, "price_usd": item.price_usd, "review_score": item.review_score} for item in comparables])
        opportunity = analyze_developer_opportunity(
            snapshot,
            review_analysis,
            forecast,
            len(fits),
            len(comparables),
            creator_scores=tuple(fit.score for fit in fits),
        )

        self.assertTrue(market.comparable_games)
        self.assertGreaterEqual(opportunity.score, 0)
        self.assertLessEqual(opportunity.score, 100)
        self.assertTrue(opportunity.reasons)


if __name__ == "__main__":
    unittest.main()

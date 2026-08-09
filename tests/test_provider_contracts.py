from datetime import datetime, timezone

import pytest

from gamepulse.providers.contracts import GameIdentity, ProviderMetric
from gamepulse.providers.steam_public import SteamCurrentPlayersProvider
from gamepulse.providers.steamspy import SteamSpyProvider, parse_owners_range


def test_provider_metric_requires_provenance():
    with pytest.raises(TypeError):
        ProviderMetric(metric="current_players", value=10)  # type: ignore[call-arg]


def test_steam_public_normalizes_current_players():
    observed = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)
    provider = SteamCurrentPlayersProvider(
        fetch_json=lambda url, timeout: {"response": {"player_count": 1234, "result": 1}},
        clock=lambda: observed,
    )
    metrics = provider.fetch(GameIdentity(steam_app_id=10, name="Counter-Strike"))
    assert len(metrics) == 1
    assert metrics[0].metric == "current_players"
    assert metrics[0].value == 1234
    assert metrics[0].source_name == "Steam Web API"
    assert metrics[0].confidence == "high"


def test_steam_public_fetches_bounded_positive_and_negative_review_excerpts():
    observed = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)
    payloads = iter(
        [
            {"success": 1, "reviews": [{"recommendationid": "p1", "review": "Great game", "votes_up": 4, "votes_funny": 1, "timestamp_created": 100}]},
            {"success": 1, "reviews": [{"recommendationid": "n1", "review": "Bad ending", "votes_up": 2, "timestamp_created": 90}]},
        ]
    )
    provider = SteamCurrentPlayersProvider(fetch_json=lambda url, timeout: next(payloads), clock=lambda: observed)

    excerpts = provider.fetch_reviews(GameIdentity(steam_app_id=10, name="Counter-Strike"))

    assert [(item.recommended, item.text) for item in excerpts] == [(True, "Great game"), (False, "Bad ending")]
    assert excerpts[0].source_name == "Steam Store reviews"
    assert excerpts[0].source_mode == "public_store_api"
    assert "review_type=positive" in excerpts[0].source_url
    assert "language=english" in excerpts[0].source_url
    assert excerpts[1].review_id == "steam-public:10:n1"


def test_steamspy_owners_are_estimates_not_sales():
    observed = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)
    provider = SteamSpyProvider(
        fetch_json=lambda url, timeout: {"appid": 10, "owners": "1,000 .. 2,000"},
        clock=lambda: observed,
    )
    metrics = provider.fetch(GameIdentity(steam_app_id=10, name="Counter-Strike"))
    names = {item.metric for item in metrics}
    assert names == {"owners_low_estimate", "owners_high_estimate"}
    assert "sales" not in " ".join(names)
    assert parse_owners_range("1,000 .. 2,000") == (1000, 2000)

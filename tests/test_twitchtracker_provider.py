from datetime import datetime, timezone

from gamepulse.providers.contracts import GameIdentity
from gamepulse.providers.twitchtracker import TwitchTrackerProvider


def test_twitchtracker_normalizes_30_day_game_summary():
    observed = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)
    seen = {}

    def fetch(url: str, timeout: float):
        seen["url"] = url
        return {"rank": 12, "hours_watched": 3000, "avg_viewers": 100, "avg_channels": 10}

    metrics = TwitchTrackerProvider(fetch_json=fetch, clock=lambda: observed).fetch(
        GameIdentity(steam_app_id=10, name="Counter Strike")
    )
    values = {item.metric: item.value for item in metrics}
    assert "Counter%20Strike" in seen["url"]
    assert values["twitch_rank_30d"] == 12
    assert values["hours_watched_30d"] == 3000
    assert values["average_viewers_30d"] == 100
    assert values["average_channels_30d"] == 10
    assert values["viewer_channel_ratio_30d"] == 10
    assert all(item.source_mode == "public_30d_summary" for item in metrics)

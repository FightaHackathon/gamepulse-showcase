from datetime import datetime, timezone

from gamepulse.providers.composite import CompositeGameSignalProvider
from gamepulse.providers.contracts import GameIdentity, ProviderMetric


OBSERVED = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)


class GoodProvider:
    provider_name = "Good"

    def fetch(self, game):
        return [ProviderMetric("current_players", 10, OBSERVED, "Good", "fixture", "high")]


class BrokenProvider:
    provider_name = "Broken"

    def fetch(self, game):
        raise RuntimeError("provider unavailable")


def test_composite_keeps_successful_metrics_when_one_provider_fails():
    report = CompositeGameSignalProvider([GoodProvider(), BrokenProvider()]).fetch_with_report(
        GameIdentity(steam_app_id=10, name="Counter-Strike")
    )
    assert [item.metric for item in report.metrics] == ["current_players"]
    assert len(report.failures) == 1
    assert report.failures[0].provider_name == "Broken"

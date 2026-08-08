"""Configuration seam for a future documented Streams Charts integration.

GamePulse intentionally does not guess undocumented endpoints or scrape pages.
A production provider can implement the source-neutral contracts here once
official API documentation/credentials are available.
"""

from __future__ import annotations

from gamepulse.providers.contracts import CreatorSignal, GameSignal, SignalSnapshot


class StreamsChartsProvider:
    def __init__(self, client_id: str | None = None, token: str | None = None):
        self.client_id = client_id
        self.token = token

    @property
    def available(self) -> bool:
        return False

    def get_game_trends(self) -> SignalSnapshot[GameSignal]:
        return SignalSnapshot(
            "Unavailable",
            "",
            "Streams Charts integration not configured with a documented API implementation",
            [],
            "unavailable",
        )

    def get_creators(
        self,
        game_id: str | None = None,
        game_name: str | None = None,
    ) -> SignalSnapshot[CreatorSignal]:
        return SignalSnapshot(
            "Unavailable",
            "",
            "Streams Charts integration not configured with a documented API implementation",
            [],
            "unavailable",
        )

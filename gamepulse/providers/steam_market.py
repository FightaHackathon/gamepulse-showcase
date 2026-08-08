"""Bounded public Steam market signal collector.

The collector uses public JSON endpoints and keeps verified/current signals
separate from SteamSpy ownership estimates. It does not scrape HTML pages.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Callable

from gamepulse.market_analysis import MarketSnapshot


JsonFetcher = Callable[[str, int], dict]


def _default_fetch_json(source: str, app_id: int) -> dict:
    urls = {
        "store": f"https://store.steampowered.com/api/appdetails?{urllib.parse.urlencode({'appids': app_id, 'cc': 'us', 'l': 'en'})}",
        "players": f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={app_id}",
        "steamspy": f"https://steamspy.com/api.php?request=appdetails&appid={app_id}",
    }
    request = urllib.request.Request(urls[source], headers={"User-Agent": "GamePulse prototype/0.1"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _owners_range(value: object) -> tuple[int | None, int | None]:
    values = [int(item.replace(",", "")) for item in re.findall(r"\d[\d,]*", str(value))]
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    return min(values), max(values)


class PublicSteamMarketProvider:
    def __init__(self, fetch_json: JsonFetcher | None = None):
        self.fetch_json = fetch_json or _default_fetch_json

    def collect(self, app_id: int) -> MarketSnapshot:
        store = self.fetch_json("store", app_id)
        store_data = store.get(str(app_id), {}).get("data", {})
        price = store_data.get("price_overview", {})
        players = self.fetch_json("players", app_id).get("response", {})
        steamspy = self.fetch_json("steamspy", app_id)
        owners_low, owners_high = _owners_range(steamspy.get("owners"))
        discount_pct = price.get("discount_percent")
        return MarketSnapshot(
            steam_app_id=int(app_id),
            seller_rank=None,
            owners_low=owners_low,
            owners_high=owners_high,
            price_usd=round(int(price["final"]) / 100, 2) if price.get("final") is not None else None,
            total_reviews=int(store_data.get("recommendations", {}).get("total", 0)) or None,
            peak_ccu=int(players.get("player_count", 0)) or None,
            source_mode="Live",
            source_name="Steam Store appdetails + Steam current players + SteamSpy estimate",
            observed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            source_url="https://store.steampowered.com/api/appdetails; https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers; https://steamspy.com/api.php",
            collection_method="bounded public JSON endpoint requests",
            confidence="mixed-public",
            discount_pct=float(discount_pct) if discount_pct is not None else None,
            player_metric="current",
        )

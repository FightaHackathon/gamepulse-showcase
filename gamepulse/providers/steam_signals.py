"""Source-neutral game signals derived from GamePulse's prepared Steam data."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from gamepulse.database import connect_read_only
from gamepulse.providers.contracts import GameSignal, SignalSnapshot


_MONTH_SECONDS = 30 * 24 * 60 * 60


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _database_observed_at(path: Path) -> str:
    try:
        timestamp = path.stat().st_mtime
    except OSError:
        timestamp = 0.0
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _review_momentum(connection: sqlite3.Connection) -> dict[int, tuple[float | None, int, int]]:
    """Return normalized recent-vs-prior review activity for each Steam app."""

    try:
        rows = connection.execute(
            """WITH latest AS (
                   SELECT steam_app_id, MAX(created_at_unix) AS latest_at
                   FROM reviews
                   WHERE created_at_unix IS NOT NULL
                   GROUP BY steam_app_id
               )
               SELECT r.steam_app_id,
                      SUM(CASE WHEN r.created_at_unix > l.latest_at - ? THEN 1 ELSE 0 END) AS recent_count,
                      SUM(CASE WHEN r.created_at_unix <= l.latest_at - ?
                                AND r.created_at_unix > l.latest_at - ? THEN 1 ELSE 0 END) AS prior_count
               FROM reviews r
               JOIN latest l ON l.steam_app_id = r.steam_app_id
               GROUP BY r.steam_app_id""",
            (_MONTH_SECONDS, _MONTH_SECONDS, _MONTH_SECONDS * 2),
        ).fetchall()
    except sqlite3.Error:
        return {}

    output: dict[int, tuple[float | None, int, int]] = {}
    for row in rows:
        app_id = int(row[0])
        recent = max(0, int(row[1] or 0))
        prior = max(0, int(row[2] or 0))
        if recent + prior == 0:
            score = None
        else:
            change = (recent - prior) / max(prior, 1)
            score = _clamp(0.5 + max(-1.0, min(1.0, change)) * 0.5)
        output[app_id] = (score, recent, prior)
    return output


class SteamPublicGameSignalProvider:
    """Read GamePulse's local SQLite dataset; no Steam credential is required."""

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

    def get_game_trends(self) -> SignalSnapshot[GameSignal]:
        if not self.database_path.exists():
            return SignalSnapshot(
                "Unavailable",
                "",
                "GamePulse prepared Steam/public data",
                [],
                "unavailable",
            )
        connection = connect_read_only(self.database_path)
        try:
            rows = connection.execute(
                """SELECT g.steam_app_id, g.name, g.peak_ccu AS prepared_peak_ccu,
                          g.review_score, g.discount_pct,
                          m.peak_ccu AS market_player_value,
                          m.player_metric, m.observed_at AS market_observed_at,
                          m.source_name AS market_source_name,
                          m.confidence AS market_confidence
                   FROM games g
                   LEFT JOIN steam_market_snapshots m
                     ON m.steam_app_id = g.steam_app_id
                    AND m.observed_at = (
                        SELECT MAX(m2.observed_at)
                        FROM steam_market_snapshots m2
                        WHERE m2.steam_app_id = g.steam_app_id
                    )
                   ORDER BY g.steam_app_id"""
            ).fetchall()
            tags: dict[int, list[str]] = defaultdict(list)
            genres: dict[int, list[str]] = defaultdict(list)
            try:
                for item in connection.execute("SELECT steam_app_id, value FROM game_tags ORDER BY steam_app_id, value"):
                    tags[int(item[0])].append(str(item[1]))
                for item in connection.execute("SELECT steam_app_id, value FROM game_genres ORDER BY steam_app_id, value"):
                    genres[int(item[0])].append(str(item[1]))
            except sqlite3.Error:
                pass
            momentum = _review_momentum(connection)
        finally:
            connection.close()

        prepared_at = _database_observed_at(self.database_path)
        signals: list[GameSignal] = []
        for row in rows:
            app_id = int(row[0])
            market_value = row[5]
            prepared_peak = row[2]
            player_metric = str(row[6] or "").casefold()
            if market_value is not None:
                audience_value = max(0.0, float(market_value))
                audience_metric = "steam_current_players" if player_metric == "current" else "steam_peak_ccu"
                observed_at = str(row[7] or prepared_at)
                source_name = str(row[8] or "GamePulse prepared Steam/public market snapshot")
                confidence = str(row[9] or "prepared")
            elif prepared_peak is not None:
                audience_value = max(0.0, float(prepared_peak))
                audience_metric = "steam_peak_ccu_prepared"
                observed_at = prepared_at
                source_name = "GamePulse prepared Steam catalogue data"
                confidence = "prepared"
            else:
                audience_value = None
                audience_metric = None
                observed_at = prepared_at
                source_name = "GamePulse prepared Steam catalogue data"
                confidence = "prepared"

            growth_score, recent_reviews, prior_reviews = momentum.get(app_id, (None, 0, 0))
            review_score = row[3]
            discount_pct = row[4]
            promotion = None if discount_pct is None else _clamp(float(discount_pct) / 100.0)
            metadata = (
                ("recent_30d_reviews", str(recent_reviews)),
                ("prior_30d_reviews", str(prior_reviews)),
            )
            signals.append(
                GameSignal(
                    game_id=str(app_id),
                    name=str(row[1]),
                    audience_value=audience_value,
                    audience_metric=audience_metric,
                    competition_value=None,
                    competition_metric=None,
                    growth_score=growth_score,
                    tags=tuple(tags.get(app_id, ())),
                    genres=tuple(genres.get(app_id, ())),
                    platform="Steam",
                    source_name=source_name,
                    observed_at=observed_at,
                    confidence=confidence,
                    source_mode="Prepared",
                    sentiment_score=(None if review_score is None else _clamp(float(review_score))),
                    promotion_score=promotion,
                    metadata=metadata,
                )
            )

        observed_values = [signal.observed_at for signal in signals if signal.observed_at]
        snapshot_observed_at = max(observed_values, default=prepared_at)
        return SignalSnapshot(
            "Prepared",
            snapshot_observed_at,
            "GamePulse prepared Steam/public signals",
            signals,
            "prepared",
        )

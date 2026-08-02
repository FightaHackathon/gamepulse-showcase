"""Explainable content-based recommendations for Player Mode."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


DiscoveryMode = Literal["best_matches", "hidden_gems"]


@dataclass(frozen=True)
class PlayerPreferences:
    preferred_tags: tuple[str, ...] = ()
    preferred_genres: tuple[str, ...] = ()
    max_price_usd: float | None = None
    operating_system: str | None = None
    discovery_mode: DiscoveryMode = "best_matches"


@dataclass(frozen=True)
class ScoreComponents:
    tag_match: float
    genre_match: float
    preference_match: float
    review_quality: float
    price_fit: float
    platform_fit: float

    @property
    def total(self) -> int:
        raw = (
            self.tag_match * 30
            + self.genre_match * 20
            + self.preference_match * 20
            + self.review_quality * 15
            + self.price_fit * 5
            + self.platform_fit * 10
        )
        return max(0, min(100, round(raw)))


def score_band(score: int) -> str:
    if score >= 85:
        return "Excellent match"
    if score >= 70:
        return "Strong match"
    return "Worth exploring"


@dataclass(frozen=True)
class Recommendation:
    app_id: int
    name: str
    match_score: int
    score_band: str
    reasons: tuple[str, ...]
    price_usd: float | None
    review_score: float | None
    release_year: str | None = None
    header_image_url: str | None = None
    owners_low: int | None = None
    owners_high: int | None = None
    windows: bool | None = None
    mac: bool | None = None
    linux: bool | None = None
    steam_store_url: str = ""
    components: ScoreComponents | None = None

    @property
    def score(self) -> float:
        """Backward-compatible normalized value for older non-Player callers."""
        return self.match_score / 100


class RecommendationEngine:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _values(self, connection: sqlite3.Connection, table: str, app_id: int) -> set[str]:
        return {row[0].casefold() for row in connection.execute(f"SELECT value FROM {table} WHERE steam_app_id = ?", (app_id,))}

    @staticmethod
    def _supports_os(row: sqlite3.Row, operating_system: str | None) -> bool:
        if not operating_system:
            return True
        columns = set(row.keys())
        key = {"windows": "windows", "macos": "mac", "mac": "mac", "linux": "linux"}.get(operating_system.casefold())
        if key is None or key not in columns:
            return True
        return bool(row[key])

    def recommend_similar(self, app_id: int, preferences: PlayerPreferences, excluded_app_ids: set[int] | None = None, limit: int = 10) -> list[Recommendation]:
        excluded = set(excluded_app_ids or ()) | {app_id}
        connection = self._connection()
        try:
            seed_tags = self._values(connection, "game_tags", app_id)
            seed_genres = self._values(connection, "game_genres", app_id)
            rows = connection.execute("SELECT * FROM games WHERE steam_app_id != ? AND (total_reviews IS NULL OR total_reviews >= 1) ORDER BY total_reviews DESC LIMIT 5000", (app_id,)).fetchall()
            recommendations = []
            by_name: dict[str, Recommendation] = {}
            for row in rows:
                candidate_id = int(row["steam_app_id"])
                if candidate_id in excluded:
                    continue
                if not self._supports_os(row, preferences.operating_system):
                    continue
                price = row["price_usd"]
                if preferences.max_price_usd is not None and (price is None or price > preferences.max_price_usd):
                    continue
                tags = self._values(connection, "game_tags", candidate_id)
                genres = self._values(connection, "game_genres", candidate_id)
                tag_overlap = len(seed_tags & tags)
                genre_overlap = len(seed_genres & genres)
                preference_overlap = len({item.casefold() for item in preferences.preferred_tags} & tags) + len({item.casefold() for item in preferences.preferred_genres} & genres)
                if tag_overlap == 0 and genre_overlap == 0 and preference_overlap == 0:
                    continue
                owners_high = row["owners_high"]
                if preferences.discovery_mode == "hidden_gems" and owners_high is not None and int(owners_high) >= 5_000_000:
                    continue
                review_score = max(0.0, min(1.0, float(row["review_score"] or 0)))
                preference_total = len(preferences.preferred_tags) + len(preferences.preferred_genres)
                components = ScoreComponents(
                    tag_match=min(1.0, tag_overlap / max(len(seed_tags), 1)),
                    genre_match=min(1.0, genre_overlap / max(len(seed_genres), 1)),
                    preference_match=min(1.0, preference_overlap / max(preference_total, 1)),
                    review_quality=review_score,
                    price_fit=1.0 if preferences.max_price_usd is not None else 0.7,
                    platform_fit=1.0 if preferences.operating_system else 0.7,
                )
                score = components.total
                if preferences.discovery_mode == "hidden_gems":
                    if owners_high is not None and int(owners_high) <= 250_000:
                        score += 10
                    elif owners_high is not None and int(owners_high) <= 1_000_000:
                        score += 5
                    elif owners_high is not None:
                        score -= 10
                    score = max(0, min(100, score))
                if score < 55:
                    continue
                reasons = []
                if preference_overlap:
                    reasons.append("matches your selected preferences")
                if tag_overlap or genre_overlap:
                    reasons.append(f"shares {tag_overlap} tag(s) and {genre_overlap} genre(s) with the selected game")
                if review_score >= 0.8:
                    reasons.append(f"strong review score ({review_score:.0%})")
                if preferences.operating_system:
                    reasons.append(f"supports {preferences.operating_system}")
                if preferences.discovery_mode == "hidden_gems" and owners_high is not None:
                    reasons.append("lower estimated audience estimate")
                reasons = reasons[:3]
                recommendation = Recommendation(
                    app_id=candidate_id,
                    name=row["name"],
                    match_score=score,
                    score_band=score_band(score),
                    reasons=tuple(reasons),
                    price_usd=price,
                    review_score=row["review_score"],
                    release_year=str(row["release_date"])[:4] if row["release_date"] else None,
                    header_image_url=row["header_image_url"],
                    owners_low=row["owners_low"],
                    owners_high=row["owners_high"],
                    windows=bool(row["windows"]) if "windows" in row.keys() and row["windows"] is not None else None,
                    mac=bool(row["mac"]) if "mac" in row.keys() and row["mac"] is not None else None,
                    linux=bool(row["linux"]) if "linux" in row.keys() and row["linux"] is not None else None,
                    steam_store_url=f"https://store.steampowered.com/app/{candidate_id}",
                    components=components,
                )
                name_key = str(row["name"]).casefold().strip()
                previous = by_name.get(name_key)
                if previous is None or recommendation.match_score > previous.match_score or (recommendation.match_score == previous.match_score and recommendation.app_id < previous.app_id):
                    by_name[name_key] = recommendation
            recommendations = list(by_name.values())
            recommendations.sort(key=lambda item: (-item.match_score, item.name.casefold(), item.app_id))
            return recommendations[: max(1, min(limit, 50))]
        finally:
            connection.close()

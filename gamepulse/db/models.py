from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GameModel(Base):
    __tablename__ = "games"

    steam_app_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    release_date: Mapped[str | None] = mapped_column(String(128))
    price_usd: Mapped[float | None] = mapped_column(Float)
    discount_pct: Mapped[float | None] = mapped_column(Float)
    required_age: Mapped[int | None] = mapped_column(Integer)
    owners_low: Mapped[int | None] = mapped_column(BigInteger)
    owners_high: Mapped[int | None] = mapped_column(BigInteger)
    peak_ccu: Mapped[int | None] = mapped_column(BigInteger)
    positive_reviews: Mapped[int | None] = mapped_column(BigInteger)
    negative_reviews: Mapped[int | None] = mapped_column(BigInteger)
    total_reviews: Mapped[int | None] = mapped_column(BigInteger)
    review_score: Mapped[float | None] = mapped_column(Float)
    recommendations: Mapped[int | None] = mapped_column(BigInteger)
    average_playtime_minutes: Mapped[float | None] = mapped_column(Float)
    median_playtime_minutes: Mapped[float | None] = mapped_column(Float)
    windows: Mapped[bool | None] = mapped_column(Boolean)
    mac: Mapped[bool | None] = mapped_column(Boolean)
    linux: Mapped[bool | None] = mapped_column(Boolean)
    metacritic_score: Mapped[float | None] = mapped_column(Float)
    header_image_url: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    short_description: Mapped[str | None] = mapped_column(Text)


class GameTagModel(Base):
    __tablename__ = "game_tags"

    steam_app_id: Mapped[int] = mapped_column(ForeignKey("games.steam_app_id", ondelete="CASCADE"), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), primary_key=True)


class GameGenreModel(Base):
    __tablename__ = "game_genres"

    steam_app_id: Mapped[int] = mapped_column(ForeignKey("games.steam_app_id", ondelete="CASCADE"), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), primary_key=True)


class ReviewSummaryModel(Base):
    __tablename__ = "review_summaries"

    steam_app_id: Mapped[int] = mapped_column(ForeignKey("games.steam_app_id", ondelete="CASCADE"), primary_key=True)
    review_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    recommended_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    not_recommended_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    review_score: Mapped[float | None] = mapped_column(Float)
    helpful_votes_total: Mapped[int | None] = mapped_column(BigInteger)
    funny_votes_total: Mapped[int | None] = mapped_column(BigInteger)
    average_word_count: Mapped[float | None] = mapped_column(Float)
    average_playtime_minutes: Mapped[float | None] = mapped_column(Float)
    latest_review_created_at_unix: Mapped[int | None] = mapped_column(BigInteger)


class ReviewModel(Base):
    """Raw review records retained by the historical catalog import."""

    __tablename__ = "reviews"

    review_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    steam_app_id: Mapped[int] = mapped_column(ForeignKey("games.steam_app_id", ondelete="CASCADE"), index=True)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer)
    recommended: Mapped[bool | None] = mapped_column(Boolean)
    helpful_votes: Mapped[int | None] = mapped_column(BigInteger)
    funny_votes: Mapped[int | None] = mapped_column(BigInteger)
    created_at_unix: Mapped[int | None] = mapped_column(BigInteger, index=True)
    author_playtime_minutes: Mapped[int | None] = mapped_column(BigInteger)
    source_game_name: Mapped[str | None] = mapped_column(String(512))
    source_price: Mapped[float | None] = mapped_column(Float)
    source_release_date: Mapped[str | None] = mapped_column(String(128))
    source_name: Mapped[str] = mapped_column(String(128), nullable=False, default="GamePulse prototype SQLite")
    source_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="historical_import")
    source_url: Mapped[str | None] = mapped_column(Text)


class SteamSnapshotModel(Base):
    __tablename__ = "steam_snapshots"
    __table_args__ = (
        UniqueConstraint("steam_app_id", "metric", "observed_at", "source_name", name="uq_steam_snapshot_metric"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    steam_app_id: Mapped[int] = mapped_column(ForeignKey("games.steam_app_id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(96), index=True)
    value_numeric: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)


class StreamingSnapshotModel(Base):
    __tablename__ = "streaming_snapshots"
    __table_args__ = (
        UniqueConstraint("steam_app_id", "metric", "observed_at", "source_name", name="uq_streaming_snapshot_metric"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    steam_app_id: Mapped[int | None] = mapped_column(ForeignKey("games.steam_app_id", ondelete="CASCADE"), index=True)
    external_game_id: Mapped[str | None] = mapped_column(String(255), index=True)
    game_name: Mapped[str | None] = mapped_column(String(512))
    metric: Mapped[str] = mapped_column(String(96), index=True)
    value_numeric: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)


class SteamSpySnapshotModel(Base):
    __tablename__ = "steamspy_snapshots"
    __table_args__ = (
        UniqueConstraint("steam_app_id", "observed_at", "source_name", name="uq_steamspy_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    steam_app_id: Mapped[int] = mapped_column(ForeignKey("games.steam_app_id", ondelete="CASCADE"), index=True)
    owners_low: Mapped[int | None] = mapped_column(BigInteger)
    owners_high: Mapped[int | None] = mapped_column(BigInteger)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)


class TrendScoreModel(Base):
    __tablename__ = "trend_scores"
    __table_args__ = (
        UniqueConstraint("steam_app_id", "audience", "observed_at", name="uq_trend_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    steam_app_id: Mapped[int] = mapped_column(ForeignKey("games.steam_app_id", ondelete="CASCADE"), index=True)
    audience: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    components: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(128), default="GamePulse", nullable=False)
    source_mode: Mapped[str] = mapped_column(String(64), default="derived", nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)


class ProviderRunModel(Base):
    __tablename__ = "provider_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_text: Mapped[str | None] = mapped_column(Text)
    metrics_written: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

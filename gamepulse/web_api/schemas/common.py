from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MetricResponse(BaseModel):
    metric: str
    value_numeric: float | None = None
    value_text: str | None = None
    observed_at: datetime
    source_name: str
    source_mode: str
    confidence: str
    source_url: str | None = None
    signal_type: str


class ReviewExcerptResponse(BaseModel):
    text: str
    helpful_votes: int | None = None
    created_at_unix: int | None = None


class ReviewExcerptsResponse(BaseModel):
    positive: list[ReviewExcerptResponse] = Field(default_factory=list)
    negative: list[ReviewExcerptResponse] = Field(default_factory=list)


class GameDetailResponse(BaseModel):
    steam_app_id: int
    name: str
    release_date: str | None = None
    price_usd: float | None = None
    owners_low: int | None = None
    owners_high: int | None = None
    peak_ccu: int | None = None
    positive_reviews: int | None = None
    negative_reviews: int | None = None
    total_reviews: int | None = None
    review_score: float | None = None
    header_image_url: str | None = None
    short_description: str | None = None
    tags: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    steam_store_url: str
    metrics: list[MetricResponse] = Field(default_factory=list)
    review_excerpts: ReviewExcerptsResponse = Field(default_factory=ReviewExcerptsResponse)
    refresh_status: str = "not_requested"
    refresh_providers: list[dict] = Field(default_factory=list)


class HistoryResponse(BaseModel):
    steam_app_id: int
    metric: str
    points: list[MetricResponse] = Field(default_factory=list)


class SourceStatusResponse(BaseModel):
    provider_name: str
    state: str
    freshness: str
    latest_status: str | None = None
    latest_success_at: datetime | None = None
    latest_failure_at: datetime | None = None
    metrics_written: int = 0
    last_error: str | None = None


class SourcesResponse(BaseModel):
    sources: list[SourceStatusResponse] = Field(default_factory=list)

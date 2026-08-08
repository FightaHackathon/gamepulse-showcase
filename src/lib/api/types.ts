export type MetricValue = {
  metric: string;
  value_numeric: number | null;
  value_text: string | null;
  observed_at: string;
  source_name: string;
  source_mode: string;
  confidence: string;
  source_url: string | null;
  signal_type: "steam" | "streaming" | "steamspy" | string;
};

export type GameDetail = {
  steam_app_id: number;
  name: string;
  release_date: string | null;
  price_usd: number | null;
  owners_low: number | null;
  owners_high: number | null;
  peak_ccu: number | null;
  total_reviews: number | null;
  review_score: number | null;
  header_image_url: string | null;
  short_description: string | null;
  tags: string[];
  genres: string[];
  steam_store_url: string;
  metrics: MetricValue[];
};

export type GameHistory = {
  steam_app_id: number;
  metric: string;
  points: MetricValue[];
};

export type SourceStatus = {
  provider_name: string;
  state: "healthy" | "degraded" | "stale" | "error" | string;
  freshness: "fresh" | "stale" | string;
  latest_status: string | null;
  latest_success_at: string | null;
  latest_failure_at: string | null;
  metrics_written: number;
  last_error: string | null;
};

export type SourcesResponse = {
  sources: SourceStatus[];
};

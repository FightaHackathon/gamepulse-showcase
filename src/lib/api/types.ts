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

export type PlayerFactor = {
  score: number | null;
  weight: number;
};

export type PlayerRecommendation = {
  app_id: number;
  steam_app_id: number;
  name: string;
  score: number;
  header_image_url: string | null;
  review_score: number | null;
  current_players: number | null;
  steam_store_url: string;
  explanation: string;
  factor_breakdown: {
    personal_fit: PlayerFactor;
    reviews: PlayerFactor;
    activity: PlayerFactor;
    momentum: PlayerFactor;
  };
};

export type PlayerAnalyzeResponse = {
  recommendations: PlayerRecommendation[];
  profile: string;
  source_name: string;
  library_complete: boolean;
};

export type StreamerRecommendation = {
  steam_app_id: number;
  name: string;
  header_image_url: string | null;
  steam_store_url: string;
  opportunity_score: number;
  breakdown: Record<string, number>;
  evidence: string[];
  reason: string;
};

export type StreamerSimulationResponse = {
  simulator: boolean;
  mode: string;
  recommendations: StreamerRecommendation[];
};

export type DeveloperOpportunity = {
  steam_app_id: number;
  name: string;
  genre: string[];
  score: number;
  signals: Record<string, number>;
  evidence: string[];
  header_image_url: string | null;
  steam_store_url: string;
};

export type DeveloperOpportunitiesResponse = {
  opportunities: DeveloperOpportunity[];
};

export type DeveloperConceptResponse = {
  data_evidence: {
    selected_game: string;
    signals: Record<string, number>;
    observations: string[];
  };
  ai_generated_idea: {
    title: string;
    genre: string;
    gameplay_loop: string;
    mechanics: string[];
    target_player: string;
    multiplayer_or_solo: string;
    steam_price_range: string;
    comparable_games: string[];
    opportunity_score: number;
    risks: string[];
  };
};

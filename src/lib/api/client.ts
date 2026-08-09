import type {
  DeveloperConceptResponse,
  DeveloperOpportunitiesResponse,
  GameDetail,
  GameHistory,
  PlayerAnalyzeResponse,
  SourceStatus,
  SourcesResponse,
  StreamerSimulationResponse,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function serverApiBaseUrl() {
  const configured = process.env.GAMEPULSE_API_BASE_URL ?? process.env.NEXT_PUBLIC_GAMEPULSE_API_BASE_URL;
  if (configured) return configured.replace(/\/$/, "");
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  return "http://localhost:3000";
}

function apiUrl(path: string) {
  if (typeof window !== "undefined") return path;
  return `${serverApiBaseUrl()}${path}`;
}

function safeErrorMessage(status: number, path: string) {
  if (path === "/api/player/analyze") {
    if (status === 404) return "The GamePulse player service route was not found. Check that the local API is running.";
    if (status === 422) return "The Steam profile or API key could not be validated.";
  }
  if (status === 404) return "Game not found";
  if (status === 503) return "GamePulse data is temporarily unavailable.";
  if (status === 401) return "This GamePulse request is not authorized.";
  return "GamePulse request failed.";
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (typeof init?.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(apiUrl(path), {
    ...init,
    cache: "no-store",
    headers,
  });

  if (!response.ok) {
    throw new ApiError(response.status, safeErrorMessage(response.status, path));
  }

  return (await response.json()) as T;
}

export function getGame(appId: number, refresh = false): Promise<GameDetail> {
  const suffix = refresh ? "?refresh=true" : "";
  return apiFetch<GameDetail>(`/api/games/${encodeURIComponent(String(appId))}${suffix}`);
}

export async function getGameHistory(appId: number, metric: string): Promise<GameHistory["points"]> {
  const response = await apiFetch<GameHistory>(
    `/api/games/${encodeURIComponent(String(appId))}/history?metric=${encodeURIComponent(metric)}`,
  );
  return response.points;
}

export async function getSourceStatus(): Promise<SourceStatus[]> {
  const response = await apiFetch<SourcesResponse>("/api/status/sources");
  return response.sources;
}

export function analyzePlayer(profileUrl: string, steamWebApiKey?: string, page?: number): Promise<PlayerAnalyzeResponse> {
  const body: { steam_profile_url: string; page?: number } = { steam_profile_url: profileUrl };
  if (page !== undefined) body.page = page;
  return apiFetch<PlayerAnalyzeResponse>("/api/player/analyze", {
    method: "POST",
    headers: steamWebApiKey ? { "X-GamePulse-Steam-Key": steamWebApiKey } : undefined,
    body: JSON.stringify(body),
  });
}

export function simulateStreamer(mode: string, genres: string[] = []): Promise<StreamerSimulationResponse> {
  return apiFetch<StreamerSimulationResponse>("/api/streamer/simulate", {
    method: "POST",
    body: JSON.stringify({ mode, genres }),
  });
}

export function getDeveloperOpportunities(): Promise<DeveloperOpportunitiesResponse> {
  return apiFetch<DeveloperOpportunitiesResponse>("/api/developer/opportunities");
}

export function generateDeveloperConcept(direction: string, opportunityAppId?: number): Promise<DeveloperConceptResponse> {
  return apiFetch<DeveloperConceptResponse>("/api/developer/concept", {
    method: "POST",
    body: JSON.stringify({ direction, opportunity_app_id: opportunityAppId }),
  });
}

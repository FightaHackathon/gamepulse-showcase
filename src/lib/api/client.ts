import type { GameDetail, GameHistory, SourceStatus, SourcesResponse } from "./types";

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

function safeErrorMessage(status: number) {
  if (status === 404) return "Game not found";
  if (status === 503) return "GamePulse data is temporarily unavailable.";
  if (status === 401) return "This GamePulse request is not authorized.";
  return "GamePulse request failed.";
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, safeErrorMessage(response.status));
  }

  return (await response.json()) as T;
}

export function getGame(appId: number): Promise<GameDetail> {
  return apiFetch<GameDetail>(`/api/games/${encodeURIComponent(String(appId))}`);
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

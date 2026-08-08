import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, getGame, getGameHistory, getSourceStatus } from "./client";

const gamePayload = {
  steam_app_id: 10,
  name: "Example Game",
  release_date: "2026-07-01",
  price_usd: 19.99,
  owners_low: null,
  owners_high: null,
  peak_ccu: null,
  total_reviews: 100,
  review_score: 0.9,
  header_image_url: "https://example.test/header.jpg",
  short_description: "Example",
  tags: ["Co-op"],
  genres: ["Action"],
  steam_store_url: "https://store.steampowered.com/app/10",
  metrics: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("GamePulse API client", () => {
  it("returns typed game, history and source status payloads", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(gamePayload), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ steam_app_id: 10, metric: "current_players", points: [] }), { status: 200 }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ sources: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getGame(10)).resolves.toMatchObject({ steam_app_id: 10, name: "Example Game" });
    await expect(getGameHistory(10, "current_players")).resolves.toEqual([]);
    await expect(getSourceStatus()).resolves.toEqual([]);
  });

  it("throws a safe typed 404 error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Game not found" }), { status: 404 })),
    );

    await expect(getGame(999)).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      message: "Game not found",
    } satisfies Partial<ApiError>);
  });

  it("does not expose arbitrary upstream text for a 503", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("provider secret details", { status: 503 })),
    );

    await expect(getGame(10)).rejects.toMatchObject({
      status: 503,
      message: "GamePulse data is temporarily unavailable.",
    } satisfies Partial<ApiError>);
  });
});

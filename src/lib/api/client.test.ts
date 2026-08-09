import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, analyzePlayer, getGame, getGameHistory, getSourceStatus } from "./client";

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

  it("maps player analysis failures to safe categories", async () => {
    const cases = [
      [404, "The GamePulse player service route was not found. Check that the local API is running."],
      [422, "The Steam profile or API key could not be validated."],
      [401, "This GamePulse request is not authorized."],
      [503, "GamePulse data is temporarily unavailable."],
    ] as const;

    for (const [status, message] of cases) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "provider secret" }), { status })));

      await expect(analyzePlayer("https://steamcommunity.com/id/example/", "secret-key")).rejects.toMatchObject({
        status,
        message,
      } satisfies Partial<ApiError>);
    }
  });

  it("marks JSON request bodies so Fusion POST routes can parse them", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ recommendations: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await analyzePlayer("https://steamcommunity.com/id/example/");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:3000/api/player/analyze",
      expect.objectContaining({
        body: JSON.stringify({ steam_profile_url: "https://steamcommunity.com/id/example/" }),
      }),
    );
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(request.headers).get("Accept")).toBe("application/json");
    expect(new Headers(request.headers).get("Content-Type")).toBe("application/json");
  });

  it("keeps an optional Steam key request-scoped in a header", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ recommendations: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await analyzePlayer("https://steamcommunity.com/id/example/", "runtime-only-key");

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(request.headers).get("X-GamePulse-Steam-Key")).toBe("runtime-only-key");
    expect(request.body).toBe(JSON.stringify({ steam_profile_url: "https://steamcommunity.com/id/example/" }));
  });

  it("adds a bounded player page only when requested", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ recommendations: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await analyzePlayer("https://steamcommunity.com/id/example/", undefined, 2);

    expect((fetchMock.mock.calls[0][1] as RequestInit).body).toBe(
      JSON.stringify({ steam_profile_url: "https://steamcommunity.com/id/example/", page: 2 }),
    );
  });
});

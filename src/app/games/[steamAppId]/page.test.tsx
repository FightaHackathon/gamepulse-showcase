// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getGame, getGameHistory } from "@/lib/api/client";

import GameDetailPage from "./page";

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return { ...actual, getGame: vi.fn(), getGameHistory: vi.fn() };
});

const mockedGetGame = vi.mocked(getGame);
const mockedGetGameHistory = vi.mocked(getGameHistory);

beforeEach(() => {
  mockedGetGame.mockClear();
  mockedGetGameHistory.mockClear();
  mockedGetGameHistory.mockResolvedValue([]);
  mockedGetGame.mockResolvedValue({
    steam_app_id: 10,
    name: "Example Game",
    release_date: "2026-07-01",
    price_usd: 19.99,
    owners_low: null,
    owners_high: null,
    peak_ccu: null,
    total_reviews: 12000,
    review_score: 0.91,
    positive_reviews: 10800,
    negative_reviews: 1200,
    header_image_url: "https://cdn.akamai.steamstatic.com/steam/apps/10/header.jpg",
    short_description: "A co-op action game built for repeat sessions.",
    tags: ["Co-op", "Fighting", "Video Production"],
    genres: ["Action"],
    steam_store_url: "https://store.steampowered.com/app/10",
    metrics: [
      {
        metric: "current_players",
        value_numeric: 1500,
        value_text: null,
        observed_at: "2026-08-08T06:30:00Z",
        source_name: "Steam Web API",
        source_mode: "public_api",
        confidence: "high",
        source_url: null,
        signal_type: "steam",
      },
      {
        metric: "average_viewers_30d",
        value_numeric: 450,
        value_text: null,
        observed_at: "2026-08-08T06:30:00Z",
        source_name: "TwitchTracker",
        source_mode: "public_30d_summary",
        confidence: "medium",
        source_url: null,
        signal_type: "streaming",
      },
    ],
    review_excerpts: {
      positive: [{ text: "A great co-op loop.", helpful_votes: 12, created_at_unix: 100 }],
      negative: [{ text: "The late game drags.", helpful_votes: 4, created_at_unix: 101 }],
    },
  });
});

describe("game detail page", () => {
  it("renders summary first with an explicit safe Steam link", async () => {
    render(await GameDetailPage({ params: Promise.resolve({ steamAppId: "10" }), searchParams: Promise.resolve({}) }));

    expect(screen.getByRole("heading", { name: "Example Game" })).toBeInTheDocument();
    expect(screen.getByAltText("Example Game artwork")).toBeInTheDocument();
    expect(screen.getByText("Fighting")).toBeInTheDocument();
    expect(screen.queryByText("Video Production")).not.toBeInTheDocument();
    expect(screen.getByText("$19.99")).toBeInTheDocument();
    expect(screen.getAllByText("91%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1.5K").length).toBeGreaterThan(0);
    expect(screen.getAllByText("450").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Latest cached observation").length).toBe(2);
    expect(screen.getByText("Most positive reviews")).toBeInTheDocument();
    expect(screen.getByText(/A great co-op loop/)).toBeInTheDocument();
    expect(screen.getByText("Most negative reviews")).toBeInTheDocument();
    expect(screen.getByText(/The late game drags/)).toBeInTheDocument();

    const steamLink = screen.getByRole("link", { name: "View on Steam" });
    expect(steamLink).toHaveAttribute("href", "https://store.steampowered.com/app/10");
    expect(steamLink).toHaveAttribute("target", "_blank");
    expect(steamLink).toHaveAttribute("rel", "noreferrer noopener");
  });

  it("falls back to cached Neon details when live refresh fails", async () => {
    mockedGetGame.mockRejectedValueOnce(new Error("refresh unavailable")).mockResolvedValueOnce({
      steam_app_id: 10,
      name: "Cached Game",
      release_date: null,
      price_usd: null,
      owners_low: null,
      owners_high: null,
      peak_ccu: null,
      total_reviews: null,
      review_score: null,
      header_image_url: null,
      short_description: null,
      tags: [],
      genres: [],
      steam_store_url: "https://store.steampowered.com/app/10",
      metrics: [],
      review_excerpts: { positive: [], negative: [] },
    });

    render(await GameDetailPage({ params: Promise.resolve({ steamAppId: "10" }), searchParams: Promise.resolve({}) }));

    expect(screen.getByText("Live refresh was unavailable; showing the latest Neon catalog and cached evidence.")).toBeInTheDocument();
    expect(mockedGetGame).toHaveBeenNthCalledWith(2, 10, false);
  });

});

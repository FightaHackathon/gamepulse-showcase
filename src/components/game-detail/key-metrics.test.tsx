// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { GameDetail } from "@/lib/api/types";

import { KeyMetrics } from "./key-metrics";

const game: GameDetail = {
  steam_app_id: 10,
  name: "Example Game",
  release_date: null,
  price_usd: 0,
  owners_low: null,
  owners_high: null,
  peak_ccu: 9999,
  total_reviews: null,
  review_score: null,
  header_image_url: null,
  short_description: null,
  tags: [],
  genres: [],
  steam_store_url: "https://store.steampowered.com/app/10",
  metrics: [{
    metric: "peak_ccu",
    value_numeric: 12000,
    value_text: null,
    observed_at: "2026-08-01T18:32:17Z",
    source_name: "Bundled artifact",
    source_mode: "derived_multi_signal",
    confidence: "medium",
    source_url: null,
    signal_type: "steam",
  }],
};

describe("KeyMetrics", () => {
  afterEach(cleanup);

  it("labels artifact peak CCU distinctly when current players are unavailable", () => {
    render(<KeyMetrics game={game} />);

    expect(screen.getByText("Peak CCU")).toBeInTheDocument();
    expect(screen.getByText("12K")).toBeInTheDocument();
    expect(screen.queryByText("Players now")).not.toBeInTheDocument();
    expect(screen.getByText("Bundled artifact")).toBeInTheDocument();
  });

  it("omits streaming viewers for Player-origin detail views", () => {
    render(<KeyMetrics game={game} includeStreaming={false} />);

    expect(screen.queryByText("30d avg viewers")).not.toBeInTheDocument();
  });
});

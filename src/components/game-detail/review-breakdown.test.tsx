// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReviewBreakdown } from "./review-breakdown";
import type { GameDetail } from "@/lib/api/types";

const game = {
  steam_app_id: 10,
  name: "Example Game",
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
} satisfies GameDetail;

describe("ReviewBreakdown", () => {
  it("shows an honest empty state when no raw review excerpts are cached", () => {
    render(<ReviewBreakdown game={game} />);

    expect(screen.getByRole("heading", { name: "Review excerpts" })).toBeInTheDocument();
    expect(screen.getByText("No cached positive review excerpts are available.")).toBeInTheDocument();
    expect(screen.getByText("No cached negative review excerpts are available.")).toBeInTheDocument();
  });

  it("distinguishes aggregate-only review data from raw review text", () => {
    render(<ReviewBreakdown game={{ ...game, total_reviews: 120, positive_reviews: 100, negative_reviews: 20 }} />);

    expect(screen.getByText(/Aggregate review counts are available, but no cached review text excerpts/)).toBeInTheDocument();
  });
});

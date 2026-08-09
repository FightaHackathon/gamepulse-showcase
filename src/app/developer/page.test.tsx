// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getDeveloperOpportunities } from "@/lib/api/client";

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return { ...actual, getDeveloperOpportunities: vi.fn() };
});

const mockedGetDeveloperOpportunities = vi.mocked(getDeveloperOpportunities);

afterEach(cleanup);

import DeveloperPage from "./page";

describe("Developer page", () => {
  it("labels unavailable evidence instead of rendering it as zero", async () => {
    mockedGetDeveloperOpportunities.mockResolvedValue({
      opportunities: [{
        steam_app_id: 10,
        name: "Example Game",
        genre: ["Action"],
        score: 72,
        signals: { genre_demand: null, opportunity_gap: 44, review_sentiment: 91 },
        evidence: ["Public evidence"],
        header_image_url: null,
        steam_store_url: "https://store.steampowered.com/app/10",
      }],
    });

    render(<DeveloperPage />);

    await waitFor(() => expect(screen.getByText("genre demand Unavailable")).toBeInTheDocument());
    expect(screen.queryByText("genre demand 0")).not.toBeInTheDocument();
  });

  it("separates market evidence from the concept generator", () => {
    mockedGetDeveloperOpportunities.mockResolvedValue({ opportunities: [] });
    render(<DeveloperPage />);
    expect(screen.getByRole("heading", { name: /find what to build/i })).toBeInTheDocument();
    expect(screen.getByText(/data evidence/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate concept/i })).toBeInTheDocument();
  });
});

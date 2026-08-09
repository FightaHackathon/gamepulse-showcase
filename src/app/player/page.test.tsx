// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, analyzePlayer: vi.fn() };
});

import { ApiError, analyzePlayer } from "@/lib/api/client";
import PlayerPage from "./page";

afterEach(cleanup);

describe("Player page", () => {
  it("provides explicit public-profile and keyed analysis actions", () => {
    render(<PlayerPage />);
    expect(screen.getByRole("heading", { name: /find what to play/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/steam profile/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /without a key/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /optional web api key/i })).toBeInTheDocument();
    expect(screen.getByText(/games to be visible publicly/i)).toBeInTheDocument();
  });

  it("sends no API key when public-profile analysis is selected", async () => {
    vi.mocked(analyzePlayer).mockResolvedValueOnce({ recommendations: [], profile: "example", source_name: "Public Steam games page", library_complete: false });
    render(<PlayerPage />);

    fireEvent.change(screen.getByLabelText(/steam profile/i), { target: { value: "https://steamcommunity.com/id/example/" } });
    fireEvent.change(screen.getByLabelText(/optional steam web api key/i), { target: { value: "visitor-secret" } });
    fireEvent.click(screen.getByRole("button", { name: /without a key/i }));

    await waitFor(() => expect(analyzePlayer).toHaveBeenCalledWith("https://steamcommunity.com/id/example/", undefined, 0));
  });

  it("renders the recommendation explanation as visible reason copy", async () => {
    vi.mocked(analyzePlayer).mockResolvedValueOnce({
      recommendations: [{
        app_id: 10,
        steam_app_id: 10,
        name: "Owned Game",
        score: 88,
        header_image_url: null,
        review_score: 0.9,
        current_players: 1200,
        steam_store_url: "https://store.steampowered.com/app/10",
        owned: false,
        genres: ["Action"],
        explanation: "Strong tag match; strong review quality",
        factor_breakdown: {
          personal_fit: { score: 0.95, weight: 45 },
          reviews: { score: 0.9, weight: 20 },
          activity: { score: 0.7, weight: 15 },
          momentum: { score: 0.6, weight: 20 },
        },
      }],
      profile: "example",
      source_name: "Public Steam games page",
      library_complete: false,
    });
    render(<PlayerPage />);

    fireEvent.change(screen.getByLabelText(/steam profile/i), { target: { value: "https://steamcommunity.com/id/example/" } });
    fireEvent.click(screen.getByRole("button", { name: /without a key/i }));

    await waitFor(() => expect(screen.getByText("Strong tag match; strong review quality")).toBeInTheDocument());
    expect(screen.getByText(/why this game/i)).toBeInTheDocument();
  });

  it("shows the safe API error message when player analysis fails", async () => {
    vi.mocked(analyzePlayer).mockRejectedValueOnce(
      new ApiError(404, "The GamePulse player service route was not found. Check that the local API is running."),
    );
    render(<PlayerPage />);

    fireEvent.change(screen.getByLabelText(/steam profile/i), { target: { value: "https://steamcommunity.com/id/example/" } });
    fireEvent.click(screen.getByRole("button", { name: /without a key/i }));

    await waitFor(() => {
      expect(screen.getByText("The GamePulse player service route was not found. Check that the local API is running.")).toBeInTheDocument();
    });
    expect(screen.queryByText("The profile could not be analyzed right now. Check the URL and try again.")).not.toBeInTheDocument();
  });

  it("hides owned games and filters unowned discovery progressively by Steam tag or genre", async () => {
    vi.mocked(analyzePlayer).mockResolvedValueOnce({
      recommendations: [
        {
          app_id: 10, steam_app_id: 10, name: "Owned Game", score: 99, header_image_url: null,
          review_score: 0.99, current_players: 10, steam_store_url: "https://store.steampowered.com/app/10",
          explanation: "owned", owned: true, genres: ["Action"],
          factor_breakdown: { personal_fit: { score: 1, weight: 45 }, reviews: { score: 1, weight: 20 }, activity: { score: 1, weight: 15 }, momentum: { score: 1, weight: 20 } },
        },
        ...Array.from({ length: 27 }, (_, index) => ({
          app_id: index + 20, steam_app_id: index + 20, name: `Discovery Game ${index + 1}`, score: 90 - index,
          header_image_url: null, review_score: 0.9, current_players: 100, steam_store_url: `https://store.steampowered.com/app/${index + 20}`,
          explanation: "matches", owned: false, genres: index % 2 ? ["Strategy"] : ["Action"], tags: index === 1 ? ["Fighting"] : [],
          factor_breakdown: { personal_fit: { score: 0.9, weight: 45 }, reviews: { score: 0.9, weight: 20 }, activity: { score: 0.5, weight: 15 }, momentum: { score: 0.5, weight: 20 } },
        })),
      ],
      profile: "example", source_name: "Public Steam games page", library_complete: false,
    });
    render(<PlayerPage />);

    fireEvent.change(screen.getByLabelText(/steam profile/i), { target: { value: "https://steamcommunity.com/id/example/" } });
    fireEvent.click(screen.getByRole("button", { name: /without a key/i }));

    await waitFor(() => expect(screen.getByText("Discovery Game 1")).toBeInTheDocument());
    expect(screen.queryByText("Owned Game")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /show more/i })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/filter recommendations by steam tag or genre/i), { target: { value: "Strategy" } });
    expect(screen.getByText("Discovery Game 2")).toBeInTheDocument();
    expect(screen.queryByText("Discovery Game 1")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/filter recommendations by steam tag or genre/i), { target: { value: "Fighting" } });
    expect(screen.getByText("Discovery Game 2")).toBeInTheDocument();
    expect(screen.queryByText("Discovery Game 1")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/filter recommendations by steam tag or genre/i), { target: { value: "all" } });

    fireEvent.click(screen.getByRole("button", { name: /show more/i }));
    expect(screen.getByText("Discovery Game 24")).toBeInTheDocument();
  });

  it("keeps the generic fallback for unknown failures", async () => {
    vi.mocked(analyzePlayer).mockRejectedValueOnce(new Error("provider secret"));
    render(<PlayerPage />);

    fireEvent.change(screen.getByLabelText(/steam profile/i), { target: { value: "https://steamcommunity.com/id/example/" } });
    fireEvent.click(screen.getByRole("button", { name: /without a key/i }));

    await waitFor(() => {
      expect(screen.getByText("The profile could not be analyzed right now. Check the URL and try again.")).toBeInTheDocument();
    });
    expect(screen.queryByText("provider secret")).not.toBeInTheDocument();
  });

  it("loads later bounded pages, dedupes results, and stops at the end", async () => {
    vi.mocked(analyzePlayer)
      .mockResolvedValueOnce({
        recommendations: Array.from({ length: 100 }, (_, index) => ({
          app_id: index + 1, steam_app_id: index + 1, name: `Page Game ${index + 1}`, score: 90,
          header_image_url: null, review_score: 0.9, current_players: 100, steam_store_url: `https://store.steampowered.com/app/${index + 1}`,
          explanation: "matches", owned: index === 10, genres: [index % 2 ? "Strategy" : "Action"],
          factor_breakdown: { personal_fit: { score: 0.9, weight: 45 }, reviews: { score: 0.9, weight: 20 }, activity: { score: 0.5, weight: 15 }, momentum: { score: 0.5, weight: 20 } },
        })),
        profile: "example", source_name: "Public Steam games page", library_complete: false,
        paging: { page: 0, page_size: 100, has_more: true, next_page: 1 },
      })
      .mockResolvedValueOnce({
        recommendations: [
          {
            app_id: 1, steam_app_id: 1, name: "Page Game 1", score: 90, header_image_url: null, review_score: 0.9,
            current_players: 100, steam_store_url: "https://store.steampowered.com/app/1", explanation: "duplicate", owned: false, genres: ["Action"],
            factor_breakdown: { personal_fit: { score: 0.9, weight: 45 }, reviews: { score: 0.9, weight: 20 }, activity: { score: 0.5, weight: 15 }, momentum: { score: 0.5, weight: 20 } },
          },
          {
            app_id: 101, steam_app_id: 101, name: "Page Game 101", score: 90, header_image_url: null, review_score: 0.9,
            current_players: 100, steam_store_url: "https://store.steampowered.com/app/101", explanation: "matches", owned: false, genres: ["Strategy"],
            factor_breakdown: { personal_fit: { score: 0.9, weight: 45 }, reviews: { score: 0.9, weight: 20 }, activity: { score: 0.5, weight: 15 }, momentum: { score: 0.5, weight: 20 } },
          },
        ],
        profile: "example", source_name: "Public Steam games page", library_complete: false,
        paging: { page: 1, page_size: 100, has_more: false, next_page: null },
      });
    render(<PlayerPage />);

    fireEvent.change(screen.getByLabelText(/steam profile/i), { target: { value: "https://steamcommunity.com/id/example/" } });
    fireEvent.click(screen.getByRole("button", { name: /without a key/i }));
    await waitFor(() => expect(screen.getByText("Page Game 1")).toBeInTheDocument());
    expect(screen.queryByText("Page Game 11")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /load more recommendations/i }));
    await waitFor(() => expect(screen.getByText("Page Game 101")).toBeInTheDocument());
    expect(screen.getAllByText("Page Game 1")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /load more recommendations/i })).not.toBeInTheDocument();
    expect(analyzePlayer).toHaveBeenLastCalledWith("https://steamcommunity.com/id/example/", undefined, 1);
  });
});

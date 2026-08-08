// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GameCard } from "./game-card";


describe("GameCard", () => {
  it("links internally and renders at most two supporting metrics", () => {
    render(
      <GameCard
        steamAppId={10}
        name="Example Game"
        headerImageUrl="https://cdn.akamai.steamstatic.com/steam/apps/10/header.jpg"
        primaryScore={86}
        supportingMetrics={[
          { label: "Reviews", value: "91%" },
          { label: "Players", value: "1.5K" },
          { label: "Extra", value: "hidden" },
        ]}
        reason="Strong co-op match."
      />,
    );

    expect(screen.getByRole("link", { name: /Example Game/i })).toHaveAttribute("href", "/games/10");
    expect(screen.getByText("Reviews")).toBeInTheDocument();
    expect(screen.getByText("Players")).toBeInTheDocument();
    expect(screen.queryByText("Extra")).not.toBeInTheDocument();
    expect(screen.getByText("86")).toBeInTheDocument();
  });

  it("renders a branded fallback when artwork is unavailable", () => {
    render(
      <GameCard
        steamAppId={20}
        name="No Art Game"
        headerImageUrl={null}
        primaryScore={null}
        supportingMetrics={[]}
        reason="A recommendation with missing artwork."
      />,
    );

    expect(screen.getByTestId("game-image-fallback")).toBeInTheDocument();
  });
});

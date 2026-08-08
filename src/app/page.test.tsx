// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";


describe("GamePulse landing page", () => {
  it("offers exactly the three approved mode paths", () => {
    render(<HomePage />);

    expect(screen.getByRole("heading", { name: "GamePulse" })).toBeInTheDocument();

    const modeLinks = screen.getAllByTestId("mode-card");
    expect(modeLinks).toHaveLength(3);
    expect(modeLinks.map((link) => link.getAttribute("href"))).toEqual([
      "/player",
      "/streamer",
      "/developer",
    ]);

    expect(screen.getByRole("heading", { name: "Player" })).toBeInTheDocument();
    expect(screen.getByText("Find what to play")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Streamer" })).toBeInTheDocument();
    expect(screen.getByText("Find what to stream")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Developer" })).toBeInTheDocument();
    expect(screen.getByText("Find what to build")).toBeInTheDocument();

    expect(screen.queryByText(/market trend/i)).not.toBeInTheDocument();
  });
});

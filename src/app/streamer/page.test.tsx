// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import StreamerPage from "./page";

describe("Streamer page", () => {
  it("exposes the new streamer simulator modes", () => {
    render(<StreamerPage />);
    expect(screen.getByRole("heading", { name: /find what to stream/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /balanced growth/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /discoverability/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /audience potential/i })).toBeInTheDocument();
  });
});

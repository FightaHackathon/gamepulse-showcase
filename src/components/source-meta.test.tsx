// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SourceMeta } from "./source-meta";


describe("SourceMeta", () => {
  it("shows source, relative freshness and confidence", () => {
    render(
      <SourceMeta
        sourceName="Steam Web API"
        observedAt="2026-08-08T04:30:00Z"
        confidence="high"
        now={Date.parse("2026-08-08T06:30:00Z")}
      />,
    );

    expect(screen.getByText("Steam Web API")).toBeInTheDocument();
    const relative = screen.getByText("2h ago");
    expect(relative).toBeInTheDocument();
    expect(relative.closest("time")).toHaveAttribute("datetime", "2026-08-08T04:30:00Z");
    expect(screen.getByText("high")).toBeInTheDocument();
  });
});

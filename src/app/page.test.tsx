// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("GamePulse root page", () => {
  it("renders the GamePulse brand placeholder", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { name: "GamePulse" })).toBeInTheDocument();
  });
});

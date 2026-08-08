// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PlayerPage from "./page";

describe("Player page", () => {
  it("provides a Steam profile workflow and recommendation surface", () => {
    render(<PlayerPage />);
    expect(screen.getByRole("heading", { name: /find what to play/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/steam profile/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /analyze/i })).toBeInTheDocument();
  });
});

// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DeveloperPage from "./page";

describe("Developer page", () => {
  it("separates market evidence from the concept generator", () => {
    render(<DeveloperPage />);
    expect(screen.getByRole("heading", { name: /find what to build/i })).toBeInTheDocument();
    expect(screen.getByText(/data evidence/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate concept/i })).toBeInTheDocument();
  });
});

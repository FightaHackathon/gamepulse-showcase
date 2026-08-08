// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "./app-shell";


describe("AppShell", () => {
  it("renders GamePulse branding and exactly six navigation destinations", () => {
    render(
      <AppShell>
        <div>Page content</div>
      </AppShell>,
    );

    expect(screen.getByText("GAMEPULSE")).toBeInTheDocument();
    expect(screen.getByText("Page content")).toBeInTheDocument();

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(6);
    expect(links.map((link) => link.textContent)).toEqual([
      "Home",
      "Player",
      "Streamer",
      "Developer",
      "Settings",
      "About",
    ]);
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/",
      "/player",
      "/streamer",
      "/developer",
      "/settings",
      "/about",
    ]);
  });
});

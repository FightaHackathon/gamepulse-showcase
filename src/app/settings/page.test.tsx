// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { getSourceStatus } from "@/lib/api/client";

import SettingsPage from "./page";

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return { ...actual, getSourceStatus: vi.fn() };
});

const mockedGetSourceStatus = vi.mocked(getSourceStatus);


describe("Settings page", () => {
  it("shows source readiness without Twitch or Streams Charts credential fields", async () => {
    mockedGetSourceStatus.mockResolvedValue([
      {
        provider_name: "Steam Web API",
        state: "healthy",
        freshness: "fresh",
        latest_status: "success",
        latest_success_at: "2026-08-08T06:30:00Z",
        latest_failure_at: null,
        metrics_written: 25,
        last_error: null,
      },
    ]);

    render(await SettingsPage());

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByText("Steam Web API")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Twitch Client ID/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Twitch Client Secret/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Streams Charts/i)).not.toBeInTheDocument();
  });
});

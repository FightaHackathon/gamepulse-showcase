// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";

import { sortMetricPoints, TimeSeriesChart } from "./time-series-chart";

const points = [
  {
    metric: "current_players",
    value_numeric: 200,
    value_text: null,
    observed_at: "2026-08-08T06:00:00Z",
    source_name: "Steam Web API",
    source_mode: "public_api",
    confidence: "high",
    source_url: null,
    signal_type: "steam",
  },
  {
    metric: "current_players",
    value_numeric: 100,
    value_text: null,
    observed_at: "2026-08-08T04:00:00Z",
    source_name: "Steam Web API",
    source_mode: "public_api",
    confidence: "high",
    source_url: null,
    signal_type: "steam",
  },
];

beforeAll(() => {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }

  Object.defineProperty(globalThis, "ResizeObserver", {
    configurable: true,
    writable: true,
    value: ResizeObserverStub,
  });
});

describe("TimeSeriesChart", () => {
  it("orders points chronologically without interpolating them", () => {
    expect(sortMetricPoints(points).map((point) => point.value_numeric)).toEqual([100, 200]);
  });

  it("renders an accessible chart label", () => {
    render(<TimeSeriesChart label="Steam player history" points={points} />);
    expect(screen.getByRole("img", { name: "Steam player history" })).toBeInTheDocument();
  });

  it("renders a clear empty state", () => {
    render(<TimeSeriesChart label="Steam player history" points={[]} />);
    expect(screen.getByText("Not enough historical data yet.")).toBeInTheDocument();
  });
});

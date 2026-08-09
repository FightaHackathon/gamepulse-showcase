// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MetricValue } from "@/lib/api/types";

vi.mock("@/components/charts/time-series-chart", () => ({
  TimeSeriesChart: ({ label, points }: { label: string; points: MetricValue[] }) => (
    points.filter((point) => point.value_numeric !== null).length >= 2
      ? <div role="img" aria-label={label}>server-rendered chart</div>
      : <div>Not enough historical data yet.</div>
  ),
  sortMetricPoints: () => {
    throw new Error("client chart helper invoked during server render");
  },
}));

import { PlayerActivity } from "./player-activity";
import { MetricEvidence } from "./metric-evidence";

afterEach(cleanup);

const peakPoint = {
  metric: "peak_ccu",
  value_numeric: 1200,
  value_text: null,
  observed_at: "2026-08-08T06:30:00Z",
  source_name: "Steam catalogue",
  source_mode: "cached_catalogue",
  confidence: "medium",
  source_url: null,
  signal_type: "steam",
} as const;

describe("metric evidence", () => {
  it("shows one latest peak observation without implying a trend", () => {
    render(<PlayerActivity points={[]} fallbackPoint={peakPoint} />);

    expect(screen.getByText("1.2K")).toBeInTheDocument();
    expect(screen.getByText("Peak CCU")).toBeInTheDocument();
    expect(screen.getByText(/not a trend or history/i)).toBeInTheDocument();
    expect(screen.queryByText("Players now")).not.toBeInTheDocument();
  });

  it("keeps the empty state honest when no latest metric exists", () => {
    render(<MetricEvidence chartLabel="Streaming audience history" points={[]} metricLabel="30d average viewers" />);

    expect(screen.getByText("Not enough historical data yet.")).toBeInTheDocument();
    expect(screen.queryByText("Latest cached observation")).not.toBeInTheDocument();
  });

  it("server-renders a real chart for two numeric observations without calling a client helper", () => {
    const older = { ...peakPoint, observed_at: "2026-08-07T06:30:00Z", value_numeric: 900 };
    const markup = renderToString(
      <MetricEvidence chartLabel="Peak player history" points={[peakPoint, older]} metricLabel="Peak CCU" />,
    );

    expect(markup).toContain('role="img"');
    expect(markup).toContain("server-rendered chart");
  });
});

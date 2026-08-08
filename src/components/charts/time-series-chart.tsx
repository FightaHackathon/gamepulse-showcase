"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { MetricValue } from "@/lib/api/types";

export function sortMetricPoints(points: MetricValue[]) {
  return [...points].sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at));
}

function compact(value: number) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function TimeSeriesChart({
  label,
  points,
  height = 280,
}: {
  label: string;
  points: MetricValue[];
  height?: number;
}) {
  const data = sortMetricPoints(points)
    .filter((point) => point.value_numeric !== null)
    .map((point) => ({
      observedAt: point.observed_at,
      value: point.value_numeric as number,
      source: point.source_name,
    }));

  if (data.length < 2) {
    return (
      <div className="grid min-h-52 place-items-center rounded-2xl border border-dashed border-white/[0.08] bg-white/[0.015] px-6 text-center">
        <div>
          <p className="m-0 text-sm font-medium text-zinc-400">Not enough historical data yet.</p>
          <p className="mt-2 mb-0 text-xs leading-5 text-zinc-600">GamePulse will fill this chart as cached snapshots accumulate.</p>
        </div>
      </div>
    );
  }

  return (
    <div role="img" aria-label={label} className="w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.055)" />
          <XAxis
            dataKey="observedAt"
            axisLine={false}
            tickLine={false}
            minTickGap={28}
            tick={{ fill: "#71717a", fontSize: 11 }}
            tickFormatter={(value: string) =>
              new Date(value).toLocaleDateString("en", { month: "short", day: "numeric" })
            }
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            width={48}
            tick={{ fill: "#71717a", fontSize: 11 }}
            tickFormatter={(value: number) => compact(value)}
          />
          <Tooltip
            cursor={{ stroke: "rgba(167,139,250,0.25)" }}
            contentStyle={{
              background: "#111118",
              border: "1px solid rgba(255,255,255,0.09)",
              borderRadius: 12,
              color: "#f4f4f5",
              fontSize: 12,
            }}
            labelFormatter={(value) => new Date(String(value)).toLocaleString("en")}
          />
          <Line
            type="linear"
            dataKey="value"
            stroke="var(--gp-accent)"
            strokeWidth={2.25}
            dot={false}
            activeDot={{ r: 4, fill: "#a78bfa", stroke: "#09090d", strokeWidth: 2 }}
            isAnimationActive={false}
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

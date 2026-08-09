import { SourceMeta } from "@/components/source-meta";
import { TimeSeriesChart } from "@/components/charts/time-series-chart";
import type { MetricValue } from "@/lib/api/types";

function sortMetricPoints(points: MetricValue[]) {
  return [...points].sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at));
}

function compact(value: number) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function MetricEvidence({
  chartLabel,
  points,
  fallbackPoint,
  metricLabel,
}: {
  chartLabel: string;
  points: MetricValue[];
  fallbackPoint?: MetricValue;
  metricLabel: string;
}) {
  const numericPoints = sortMetricPoints(points).filter((point) => point.value_numeric !== null);
  if (numericPoints.length >= 2) {
    return <TimeSeriesChart label={chartLabel} points={points} />;
  }

  const latest = numericPoints.at(-1) ?? (fallbackPoint?.value_numeric === null ? undefined : fallbackPoint);
  if (!latest || latest.value_numeric === null) {
    return <TimeSeriesChart label={chartLabel} points={points} />;
  }

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.015] px-6 py-6" aria-label={`${metricLabel} latest observation`}>
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="m-0 text-[0.67rem] font-semibold uppercase tracking-[0.12em] text-zinc-600">Latest cached observation</p>
          <div className="mt-2 text-[2.4rem] font-semibold tracking-[-0.05em] text-white">{compact(latest.value_numeric)}</div>
          <p className="mt-1 mb-0 text-sm text-zinc-400">{metricLabel}</p>
        </div>
        <SourceMeta sourceName={latest.source_name} observedAt={latest.observed_at} confidence={latest.confidence} />
      </div>
      <p className="mt-5 mb-0 text-xs leading-5 text-zinc-600">This is the latest available observation, not a trend or history. More cached snapshots are needed to show change over time.</p>
    </div>
  );
}

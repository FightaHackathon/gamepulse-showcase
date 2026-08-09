import { SourceMeta } from "@/components/source-meta";
import { MetricEvidence } from "@/components/game-detail/metric-evidence";
import type { MetricValue } from "@/lib/api/types";

export function PlayerActivity({ points, fallbackPoint }: { points: MetricValue[]; fallbackPoint?: MetricValue }) {
  const latest = [...points].sort((a, b) => Date.parse(b.observed_at) - Date.parse(a.observed_at))[0];
  const metric = latest?.metric ?? fallbackPoint?.metric;
  const metricLabel = metric === "peak_ccu" ? "Peak CCU" : "Players now";

  return (
    <section className="mt-16 border-t border-white/[0.07] pt-10">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="m-0 text-2xl font-semibold tracking-[-0.035em] text-white">Player activity</h2>
          <p className="mt-2 mb-0 text-sm leading-6 text-zinc-500">Cached Steam current-player observations over time.</p>
        </div>
        {latest ? (
          <SourceMeta sourceName={latest.source_name} observedAt={latest.observed_at} confidence={latest.confidence} />
        ) : null}
      </div>
      <MetricEvidence chartLabel={`${metricLabel} history`} points={points} fallbackPoint={fallbackPoint} metricLabel={metricLabel} />
    </section>
  );
}

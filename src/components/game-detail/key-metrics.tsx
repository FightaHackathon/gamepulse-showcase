import { SourceMeta } from "@/components/source-meta";
import { Card } from "@/components/ui/card";
import type { GameDetail, MetricValue } from "@/lib/api/types";

function compact(value: number | null) {
  if (value === null) return "—";
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function price(value: number | null) {
  if (value === null) return "—";
  if (value === 0) return "Free";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function reviewPercent(value: number | null) {
  if (value === null) return "—";
  const normalized = value <= 1 ? value * 100 : value;
  return `${Math.round(normalized)}%`;
}

function metric(game: GameDetail, name: string): MetricValue | undefined {
  return game.metrics.find((item) => item.metric === name);
}

function MetricCell({
  label,
  value,
  source,
}: {
  label: string;
  value: string;
  source?: MetricValue;
}) {
  return (
    <div title={label === "Peak CCU" ? "Peak CCU means peak concurrent users: the highest number of players online at the same time." : undefined} className="min-w-0 px-5 py-5 first:pl-0 last:pr-0 max-[720px]:px-0 max-[720px]:py-4">
      <div className="text-[0.67rem] font-semibold uppercase tracking-[0.12em] text-zinc-600">{label}</div>
      <div className="mt-2 text-[1.45rem] font-semibold tracking-[-0.035em] text-white">{value}</div>
      {source ? (
        <SourceMeta
          className="mt-2"
          sourceName={source.source_name}
          observedAt={source.observed_at}
          confidence={source.confidence}
        />
      ) : null}
    </div>
  );
}

export function KeyMetrics({ game, includeStreaming = true }: { game: GameDetail; includeStreaming?: boolean }) {
  const currentPlayers = metric(game, "current_players");
  const peakPlayers = metric(game, "peak_ccu");
  const playerEvidence = currentPlayers ?? peakPlayers;
  const averageViewers = metric(game, "average_viewers_30d");

  return (
    <Card className="mt-9 px-5 py-1">
      <div className={`grid ${includeStreaming ? "grid-cols-4" : "grid-cols-3"} divide-x divide-white/[0.07] max-[920px]:grid-cols-2 max-[920px]:[&>*:nth-child(odd)]:border-l-0 max-[720px]:grid-cols-1 max-[720px]:divide-x-0 max-[720px]:divide-y`}>
        <MetricCell label="Price" value={price(game.price_usd)} />
        <MetricCell label="Reviews" value={reviewPercent(game.review_score)} />
        <MetricCell label={currentPlayers ? "Players now" : "Peak CCU"} value={compact(playerEvidence?.value_numeric ?? null)} source={playerEvidence} />
        {includeStreaming ? <MetricCell label="30d avg viewers" value={compact(averageViewers?.value_numeric ?? null)} source={averageViewers} /> : null}
      </div>
    </Card>
  );
}

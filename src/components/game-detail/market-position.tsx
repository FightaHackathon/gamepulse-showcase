import { SourceMeta } from "@/components/source-meta";
import type { GameDetail } from "@/lib/api/types";

function compact(value: number) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function MarketPosition({ game }: { game: GameDetail }) {
  const low = game.metrics.find((item) => item.metric === "owners_low_estimate");
  const high = game.metrics.find((item) => item.metric === "owners_high_estimate");
  const source = low?.value_numeric != null ? low : high?.value_numeric != null ? high : undefined;
  const lowValue = low?.value_numeric ?? game.owners_low;
  const highValue = high?.value_numeric ?? game.owners_high;
  const hasRange = lowValue !== null && lowValue !== undefined && highValue !== null && highValue !== undefined;

  return (
    <section className="mt-16 border-t border-white/[0.07] pt-10 pb-16">
      <h2 className="m-0 text-2xl font-semibold tracking-[-0.035em] text-white">Market position</h2>
      <p className="mt-2 mb-0 max-w-2xl text-sm leading-6 text-zinc-500">
        A lightweight ownership signal for context. This is not verified sales, revenue, downloads, or units sold.
      </p>

      <div className="mt-7 max-w-2xl rounded-2xl border border-white/[0.07] bg-white/[0.025] p-5">
        <div className="text-[0.67rem] font-semibold uppercase tracking-[0.12em] text-zinc-600">Estimated owners</div>
        <div className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-white">
          {hasRange ? `${compact(lowValue)} – ${compact(highValue)}` : "Unavailable"}
        </div>
        {source ? (
          <SourceMeta
            className="mt-3"
            sourceName={source.source_name}
            observedAt={source.observed_at}
            confidence={source.confidence}
          />
        ) : hasRange ? (
          <p className="mt-3 mb-0 text-xs text-zinc-600">Catalog estimate; source metadata is unavailable for this value.</p>
        ) : (
          <p className="mt-3 mb-0 text-xs text-zinc-600">No current ownership estimate is cached for this game.</p>
        )}
      </div>
    </section>
  );
}

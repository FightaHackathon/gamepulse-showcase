import type { GameDetail } from "@/lib/api/types";

function percentage(value: number | null) {
  if (value === null) return null;
  return Math.max(0, Math.min(100, value <= 1 ? value * 100 : value));
}

export function ReviewBreakdown({ game }: { game: GameDetail }) {
  const score = percentage(game.review_score);
  const positive = game.positive_reviews ?? null;
  const negative = game.negative_reviews ?? null;
  const reviewTotal = positive !== null && negative !== null ? positive + negative : null;
  const excerptGroups = game.review_excerpts ?? { positive: [], negative: [] };
  const hasReviewCounts = positive !== null || negative !== null || game.total_reviews !== null;
  const formatCount = (value: number | null) => value === null ? "—" : new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);

  return (
    <section className="mt-16 border-t border-white/[0.07] pt-10">
      <h2 className="m-0 text-2xl font-semibold tracking-[-0.035em] text-white">Reviews</h2>
      <p className="mt-2 mb-0 text-sm leading-6 text-zinc-500">Steam review quality from the cached GamePulse catalogue.</p>

      <div className="mt-7 max-w-2xl">
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-[2.2rem] font-semibold tracking-[-0.05em] text-white">
              {score === null ? "—" : `${Math.round(score)}%`}
            </div>
            <div className="mt-1 text-sm text-zinc-500">
              {game.total_reviews === null
                ? "Review sample unavailable"
                : `${new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(game.total_reviews)} reviews`}
            </div>
          </div>
          <div className="text-right text-xs leading-5 text-zinc-600">Positive-share signal<br />not a GamePulse prediction</div>
        </div>
        {score !== null ? (
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/[0.055]">
            <div
              className="h-full rounded-full bg-violet-400"
              style={{ width: `${score}%` }}
              aria-hidden="true"
            />
          </div>
        ) : null}
      </div>

      <div className="mt-9 grid max-w-2xl gap-4 sm:grid-cols-2" aria-label="Positive and negative review counts">
        <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.04] p-5">
          <div className="text-[0.67rem] font-semibold uppercase tracking-[0.12em] text-emerald-300/70">Positive reviews</div>
          <div className="mt-2 text-2xl font-semibold text-white">{formatCount(positive)}</div>
          {reviewTotal !== null && positive !== null ? <div className="mt-1 text-xs text-zinc-500">{Math.round((positive / reviewTotal) * 100)}% of counted reviews</div> : null}
        </div>
        <div className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.04] p-5">
          <div className="text-[0.67rem] font-semibold uppercase tracking-[0.12em] text-rose-300/70">Negative reviews</div>
          <div className="mt-2 text-2xl font-semibold text-white">{formatCount(negative)}</div>
          {reviewTotal !== null && negative !== null ? <div className="mt-1 text-xs text-zinc-500">{Math.round((negative / reviewTotal) * 100)}% of counted reviews</div> : null}
        </div>
      </div>

      <section className="mt-12" aria-labelledby="review-excerpts-title">
        <h3 id="review-excerpts-title" className="m-0 text-xl font-semibold tracking-[-0.03em] text-white">Review excerpts</h3>
        <p className="mt-2 mb-0 text-sm leading-6 text-zinc-500">
          {hasReviewCounts && !excerptGroups.positive.length && !excerptGroups.negative.length
            ? "Aggregate review counts are available, but no cached review text excerpts are available."
            : "Up to three cached excerpts selected by their stored recommendation signal and helpful votes."}
        </p>
        <div className="mt-6 grid gap-5 lg:grid-cols-2">
          {(["positive", "negative"] as const).map((kind) => {
            const excerpts = excerptGroups[kind];
            return (
              <div key={kind} className="rounded-2xl border border-white/[0.08] bg-white/[0.015] p-5">
                <h4 className="m-0 text-sm font-semibold text-zinc-200">Most {kind} reviews</h4>
                {excerpts.length ? (
                  <div className="mt-4 grid gap-4">
                    {excerpts.map((excerpt) => <blockquote key={`${kind}-${excerpt.text}`} className="m-0 border-l border-white/15 pl-4 text-sm leading-6 text-zinc-400">“{excerpt.text}”</blockquote>)}
                  </div>
                ) : <p className="mt-4 mb-0 text-sm text-zinc-600">No cached {kind} review excerpts are available.</p>}
              </div>
            );
          })}
        </div>
      </section>
    </section>
  );
}

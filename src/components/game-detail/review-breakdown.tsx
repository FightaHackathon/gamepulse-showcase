import type { GameDetail } from "@/lib/api/types";

function percentage(value: number | null) {
  if (value === null) return null;
  return Math.max(0, Math.min(100, value <= 1 ? value * 100 : value));
}

export function ReviewBreakdown({ game }: { game: GameDetail }) {
  const score = percentage(game.review_score);

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
        <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/[0.055]">
          <div
            className="h-full rounded-full bg-violet-400"
            style={{ width: `${score ?? 0}%` }}
            aria-hidden="true"
          />
        </div>
      </div>
    </section>
  );
}

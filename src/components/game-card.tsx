import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { GameImage } from "@/components/game-image";
import { Card } from "@/components/ui/card";

export type SupportingMetric = {
  label: string;
  value: string;
};

export function GameCard({
  steamAppId,
  name,
  headerImageUrl,
  primaryScore,
  supportingMetrics,
  reason,
  href,
}: {
  steamAppId: number;
  name: string;
  headerImageUrl: string | null;
  primaryScore: number | null;
  supportingMetrics: SupportingMetric[];
  reason: string;
  href?: string;
}) {
  const visibleMetrics = supportingMetrics.slice(0, 2);

  return (
    <Link
      href={href ?? `/games/${steamAppId}`}
      className="group block rounded-[1.35rem] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/80"
    >
      <Card className="overflow-hidden transition duration-200 hover:-translate-y-1 hover:border-violet-400/20 hover:bg-white/[0.05]">
        <div className="relative aspect-[460/215] overflow-hidden bg-[#111118]">
          <GameImage src={headerImageUrl} alt={`${name} artwork`} />
          <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-[#101017] to-transparent" />
          {primaryScore !== null ? (
            <div className="absolute right-4 top-4 min-w-12 rounded-xl border border-white/10 bg-black/60 px-3 py-2 text-center backdrop-blur-md">
              <div className="text-lg font-bold leading-none text-white">{Math.round(primaryScore)}</div>
              <div className="mt-1 text-[0.6rem] font-semibold uppercase tracking-[0.12em] text-zinc-400">Score</div>
            </div>
          ) : null}
        </div>

        <div className="p-5">
          <div className="flex items-start justify-between gap-4">
            <h3 className="m-0 text-lg font-semibold tracking-[-0.025em] text-white">{name}</h3>
            <ArrowUpRight aria-hidden="true" className="mt-0.5 size-[18px] shrink-0 text-zinc-600 transition group-hover:text-violet-300" />
          </div>

          {visibleMetrics.length ? (
            <dl className="mt-5 grid grid-cols-2 gap-3 border-y border-white/[0.065] py-4">
              {visibleMetrics.map((metric) => (
                <div key={metric.label}>
                  <dt title={metric.label === "Peak CCU" ? "Peak CCU means peak concurrent users: the highest number of players online at the same time." : undefined} className="text-[0.66rem] font-semibold uppercase tracking-[0.11em] text-zinc-600">{metric.label}</dt>
                  <dd className="mt-1.5 ml-0 text-sm font-semibold text-zinc-200">{metric.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}

          <div className="mt-4 text-[0.66rem] font-semibold uppercase tracking-[0.11em] text-zinc-600">Why this game</div>
          <p className="mt-1.5 mb-0 line-clamp-3 text-sm leading-6 text-zinc-500">{reason}</p>
        </div>
      </Card>
    </Link>
  );
}

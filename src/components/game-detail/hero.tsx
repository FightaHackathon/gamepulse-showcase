import { ExternalLink } from "lucide-react";

import { GameImage } from "@/components/game-image";
import { Badge } from "@/components/ui/badge";
import type { GameDetail } from "@/lib/api/types";

export function GameDetailHero({ game }: { game: GameDetail }) {
  const labels = [...game.genres, ...game.tags].filter((value) => value.trim().toLowerCase() !== "video production").filter(
    (value, index, all) => all.findIndex((item) => item.toLowerCase() === value.toLowerCase()) === index,
  );

  return (
    <section>
      <div className="relative aspect-[16/6] min-h-[230px] overflow-hidden rounded-[1.6rem] border border-white/[0.07] bg-[#111118] shadow-[0_30px_90px_rgba(0,0,0,0.3)]">
        <GameImage src={game.header_image_url} alt={`${game.name} artwork`} sizes="(max-width: 860px) 100vw, 80vw" priority />
        <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-[#09090d] via-[#09090d]/45 to-transparent" />
      </div>

      <div className="mt-7 grid items-start gap-7 lg:grid-cols-[minmax(0,1fr)_auto]">
        <div>
          <h1 className="m-0 text-[clamp(2rem,5vw,3.75rem)] font-semibold leading-[1.02] tracking-[-0.05em] text-white">
            {game.name}
          </h1>
          {game.short_description ? (
            <p className="mt-4 mb-0 max-w-3xl text-[0.98rem] leading-7 text-zinc-400">{game.short_description}</p>
          ) : null}
          {labels.length ? (
            <div className="mt-5 flex flex-wrap gap-2">
              {labels.slice(0, 6).map((label) => (
                <Badge key={label}>{label}</Badge>
              ))}
            </div>
          ) : null}
        </div>

        <a
          href={game.steam_store_url}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-violet-500 px-5 text-sm font-semibold text-white shadow-[0_12px_34px_rgba(124,58,237,0.28)] transition hover:bg-violet-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300"
        >
          View on Steam
          <ExternalLink aria-hidden="true" className="size-4" />
        </a>
      </div>
    </section>
  );
}

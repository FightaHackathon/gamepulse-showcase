"use client";

import { useRouter } from "next/navigation";

type OwnedGame = { steamAppId: number; name: string; genres: string[] };
const OWNED_GAMES_KEY = "gamepulse.player-owned-games";

function getOwnedGames(): OwnedGame[] {
  try {
    const parsed: unknown = JSON.parse(window.sessionStorage.getItem(OWNED_GAMES_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((item): item is OwnedGame => typeof item === "object" && item !== null && typeof (item as OwnedGame).steamAppId === "number" && typeof (item as OwnedGame).name === "string" && Array.isArray((item as OwnedGame).genres)) : [];
  } catch {
    return [];
  }
}

export function PlayerOriginContext({ genres }: { genres: string[] }) {
  const router = useRouter();
  const matches = getOwnedGames().map((game) => ({ game, shared: game.genres.filter((genre) => genres.includes(genre)) })).filter(({ shared }) => shared.length).sort((a, b) => b.shared.length - a.shared.length || a.game.name.localeCompare(b.game.name)).slice(0, 3);

  return <section className="mt-7 rounded-2xl border border-violet-400/20 bg-violet-500/[0.06] p-5" aria-labelledby="player-context-title">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 id="player-context-title" className="m-0 text-lg font-semibold text-white">Why this fits your library</h2>
        {matches.length ? <ul className="mt-3 mb-0 space-y-2 pl-5 text-sm text-zinc-300">{matches.map(({ game, shared }) => <li key={game.steamAppId}><span className="font-medium text-white">{game.name}</span> shares {shared.join(", ")}.</li>)}</ul> : <p className="mt-2 mb-0 text-sm text-zinc-400">No shared genres were found among the analyzed games you own.</p>}
      </div>
      <button type="button" onClick={() => router.back()} className="min-h-10 rounded-xl border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-zinc-200 hover:border-violet-400/40 hover:bg-white/[0.07]">Back to Player</button>
    </div>
  </section>;
}

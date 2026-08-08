"use client";

import { FormEvent, useState } from "react";

import { GameCard } from "@/components/game-card";
import { Card } from "@/components/ui/card";
import { analyzePlayer } from "@/lib/api/client";
import type { PlayerRecommendation } from "@/lib/api/types";

export default function PlayerPage() {
  const [profileUrl, setProfileUrl] = useState("");
  const [steamKey, setSteamKey] = useState("");
  const [recommendations, setRecommendations] = useState<PlayerRecommendation[]>([]);
  const [status, setStatus] = useState("Enter a public Steam profile to analyze your fit.");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setStatus("Analyzing cached GamePulse signals…");
    try {
      const response = await analyzePlayer(profileUrl.trim(), steamKey.trim() || undefined);
      setRecommendations(response.recommendations);
      setStatus(`${response.source_name} · ${response.recommendations.length} recommendations ranked for this session.`);
    } catch {
      setRecommendations([]);
      setStatus("The profile could not be analyzed right now. Check the URL and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="gp-page py-3 lg:py-8">
      <div className="max-w-3xl">
        <h1 className="m-0 text-[clamp(2.2rem,5vw,3.8rem)] font-semibold tracking-[-0.055em] text-white">Find what to play</h1>
        <p className="mt-4 mb-0 text-base leading-7 text-zinc-500">Turn your Steam profile and public GamePulse signals into recommendations you can explain.</p>
      </div>

      <section className="mt-10 max-w-3xl">
        <Card className="p-6 sm:p-8">
          <form onSubmit={submit} className="grid gap-5">
            <div>
              <label htmlFor="steam-profile" className="text-sm font-semibold text-white">Steam profile URL</label>
              <input id="steam-profile" value={profileUrl} onChange={(event) => setProfileUrl(event.target.value)} placeholder="https://steamcommunity.com/id/you/" required className="mt-2 min-h-12 w-full rounded-xl border border-white/10 bg-black/20 px-4 text-sm text-white outline-none transition placeholder:text-zinc-700 focus:border-violet-400/70 focus:ring-2 focus:ring-violet-400/20" />
            </div>
            <div>
              <label htmlFor="steam-key" className="text-sm font-semibold text-white">Optional Steam Web API key</label>
              <input id="steam-key" type="password" value={steamKey} onChange={(event) => setSteamKey(event.target.value)} placeholder="Used for this request only" autoComplete="off" className="mt-2 min-h-12 w-full rounded-xl border border-white/10 bg-black/20 px-4 text-sm text-white outline-none transition placeholder:text-zinc-700 focus:border-violet-400/70 focus:ring-2 focus:ring-violet-400/20" />
            </div>
            <button type="submit" disabled={loading} className="min-h-12 rounded-xl bg-violet-500 px-5 text-sm font-semibold text-white transition hover:bg-violet-400 disabled:cursor-wait disabled:opacity-60">{loading ? "Analyzing…" : "Analyze my profile"}</button>
          </form>
          <p className="mt-5 mb-0 text-sm leading-6 text-zinc-500" aria-live="polite">{status}</p>
        </Card>
      </section>

      {recommendations.length ? (
        <section className="mt-14" aria-labelledby="player-results-title">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 id="player-results-title" className="m-0 text-2xl font-semibold tracking-[-0.035em] text-white">Recommendations</h2>
              <p className="mt-2 mb-0 text-sm text-zinc-500">Personal fit 45% · reviews 20% · activity 15% · momentum 20%</p>
            </div>
          </div>
          <div className="mt-7 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {recommendations.map((item) => (
              <GameCard key={item.steam_app_id} steamAppId={item.steam_app_id} name={item.name} headerImageUrl={item.header_image_url} primaryScore={item.score} supportingMetrics={[{ label: "Reviews", value: item.review_score === null ? "—" : `${Math.round((item.review_score <= 1 ? item.review_score * 100 : item.review_score))}%` }, { label: "Players", value: item.current_players === null ? "—" : item.current_players.toLocaleString() }]} reason={item.explanation} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

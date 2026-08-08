"use client";

import { useState } from "react";

import { Card } from "@/components/ui/card";
import { simulateStreamer } from "@/lib/api/client";
import type { StreamerRecommendation } from "@/lib/api/types";

const modes = [
  ["balanced", "Balanced Growth"],
  ["discoverability", "Discoverability"],
  ["audience_potential", "Audience Potential"],
] as const;

export default function StreamerPage() {
  const [mode, setMode] = useState<string>("balanced");
  const [genres, setGenres] = useState("");
  const [results, setResults] = useState<StreamerRecommendation[]>([]);
  const [status, setStatus] = useState("Simulate a zero-audience channel using cached category signals.");

  async function runSimulation() {
    setStatus("Comparing demand, competition, ratio, momentum, and category growth…");
    try {
      const response = await simulateStreamer(mode, genres.split(",").map((value) => value.trim()).filter(Boolean));
      setResults(response.recommendations);
      setStatus(`${response.recommendations.length} categories ranked for ${response.mode.replaceAll("_", " ")}.`);
    } catch {
      setResults([]);
      setStatus("The simulator could not load cached signals right now.");
    }
  }

  return (
    <div className="gp-page py-3 lg:py-8">
      <div className="max-w-3xl">
        <h1 className="m-0 text-[clamp(2.2rem,5vw,3.8rem)] font-semibold tracking-[-0.055em] text-white">Find what to stream</h1>
        <p className="mt-4 mb-0 text-base leading-7 text-zinc-500">New Streamer Simulator for creators starting from zero audience. No existing Twitch channel or credentials required.</p>
      </div>

      <section className="mt-10 max-w-4xl">
        <Card className="p-6 sm:p-8">
          <div className="flex flex-wrap gap-2" aria-label="Simulator mode">
            {modes.map(([value, label]) => (
              <button key={value} type="button" onClick={() => setMode(value)} aria-pressed={mode === value} className={`min-h-10 rounded-xl px-4 text-sm font-semibold transition ${mode === value ? "bg-violet-500 text-white" : "border border-white/10 bg-white/[0.03] text-zinc-400 hover:text-white"}`}>{label}</button>
            ))}
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
            <div>
              <label htmlFor="streamer-genres" className="text-sm font-semibold text-white">Game categories (optional)</label>
              <input id="streamer-genres" value={genres} onChange={(event) => setGenres(event.target.value)} placeholder="Action, Strategy, Co-op" className="mt-2 min-h-12 w-full rounded-xl border border-white/10 bg-black/20 px-4 text-sm text-white outline-none placeholder:text-zinc-700 focus:border-violet-400/70 focus:ring-2 focus:ring-violet-400/20" />
            </div>
            <button type="button" onClick={runSimulation} className="min-h-12 rounded-xl bg-violet-500 px-5 text-sm font-semibold text-white transition hover:bg-violet-400">Run simulation</button>
          </div>
          <p className="mt-5 mb-0 text-sm leading-6 text-zinc-500" aria-live="polite">{status}</p>
        </Card>
      </section>

      {results.length ? (
        <section className="mt-14" aria-labelledby="streamer-results-title">
          <h2 id="streamer-results-title" className="m-0 text-2xl font-semibold tracking-[-0.035em] text-white">Growth opportunities</h2>
          <div className="mt-7 grid gap-5 md:grid-cols-2">
            {results.map((item) => (
              <Card key={item.steam_app_id} className="p-6">
                <div className="flex items-start justify-between gap-4"><h3 className="m-0 text-lg font-semibold text-white">{item.name}</h3><span className="text-2xl font-semibold text-violet-300">{Math.round(item.opportunity_score)}</span></div>
                <p className="mt-2 text-sm text-zinc-500">Growth opportunity score</p>
                <div className="mt-6 grid grid-cols-2 gap-x-4 gap-y-4 text-sm sm:grid-cols-5">
                  {Object.entries(item.breakdown).map(([label, value]) => <div key={label}><div className="text-[0.62rem] uppercase tracking-[0.11em] text-zinc-600">{label.replaceAll("_", " ")}</div><div className="mt-1 font-semibold text-zinc-200">{Math.round(value)}</div></div>)}
                </div>
                <p className="mt-5 mb-0 text-sm leading-6 text-zinc-500">{item.reason}</p>
              </Card>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

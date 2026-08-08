"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";
import { generateDeveloperConcept, getDeveloperOpportunities } from "@/lib/api/client";
import type { DeveloperConceptResponse, DeveloperOpportunity } from "@/lib/api/types";

export default function DeveloperPage() {
  const [opportunities, setOpportunities] = useState<DeveloperOpportunity[]>([]);
  const [direction, setDirection] = useState("co-op action");
  const [concept, setConcept] = useState<DeveloperConceptResponse | null>(null);
  const [status, setStatus] = useState("Loading cached market opportunities…");

  useEffect(() => {
    getDeveloperOpportunities().then((response) => { setOpportunities(response.opportunities); setStatus("Market evidence is ready for exploration."); }).catch(() => setStatus("Market evidence is temporarily unavailable."));
  }, []);

  async function createConcept() {
    try { setConcept(await generateDeveloperConcept(direction, opportunities[0]?.steam_app_id)); } catch { setStatus("Concept generation needs the API to be available."); }
  }

  return (
    <div className="gp-page py-3 lg:py-8">
      <div className="max-w-3xl">
        <h1 className="m-0 text-[clamp(2.2rem,5vw,3.8rem)] font-semibold tracking-[-0.055em] text-white">Find what to build</h1>
        <p className="mt-4 mb-0 text-base leading-7 text-zinc-500">Move from rising genres and player growth to an opportunity direction and a clearly labeled mini-game concept.</p>
      </div>

      <div className="mt-12 grid gap-12 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <section aria-labelledby="market-opportunities-title">
          <div className="flex items-end justify-between gap-4"><div><h2 id="market-opportunities-title" className="m-0 text-2xl font-semibold tracking-[-0.035em] text-white">Market opportunities</h2><p className="mt-2 mb-0 text-sm text-zinc-500" aria-live="polite">{status}</p></div></div>
          <h3 className="mt-7 mb-0 text-[0.68rem] font-semibold uppercase tracking-[0.13em] text-violet-300">DATA EVIDENCE</h3>
          <div className="mt-4 grid gap-4">{opportunities.map((item) => <Card key={item.steam_app_id} className="p-5"><div className="flex items-start justify-between gap-4"><div><h3 className="m-0 text-base font-semibold text-white">{item.name}</h3><p className="mt-2 mb-0 text-sm text-zinc-500">{item.genre.join(" · ") || "Emerging category"}</p></div><span className="text-xl font-semibold text-violet-300">{Math.round(item.score)}</span></div><div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-xs text-zinc-500">{Object.entries(item.signals).filter(([key]) => key !== "opportunity_score").map(([key, value]) => <span key={key}>{key.replaceAll("_", " ")} {Math.round(value)}</span>)}</div><p className="mt-4 mb-0 text-sm leading-6 text-zinc-500">{item.evidence[0]}</p></Card>)}</div>
        </section>

        <section aria-labelledby="concept-title">
          <Card className="p-6 sm:p-7">
            <h2 id="concept-title" className="m-0 text-2xl font-semibold tracking-[-0.035em] text-white">Concept direction</h2>
            <label htmlFor="concept-direction" className="mt-6 block text-sm font-semibold text-white">Direction</label>
            <input id="concept-direction" value={direction} onChange={(event) => setDirection(event.target.value)} className="mt-2 min-h-12 w-full rounded-xl border border-white/10 bg-black/20 px-4 text-sm text-white outline-none focus:border-violet-400/70 focus:ring-2 focus:ring-violet-400/20" />
            <button type="button" onClick={createConcept} className="mt-4 min-h-12 w-full rounded-xl bg-violet-500 px-5 text-sm font-semibold text-white transition hover:bg-violet-400">Generate concept</button>
            {concept ? <div className="mt-8 grid gap-7"><div><h3 className="m-0 text-[0.68rem] font-semibold uppercase tracking-[0.13em] text-violet-300">DATA EVIDENCE</h3><p className="mt-3 mb-0 text-sm leading-6 text-zinc-400">{concept.data_evidence.observations.join(" ")}</p></div><div className="border-t border-white/[0.07] pt-6"><h3 className="m-0 text-[0.68rem] font-semibold uppercase tracking-[0.13em] text-violet-300">AI GENERATED IDEA</h3><h4 className="mt-3 mb-0 text-xl font-semibold text-white">{concept.ai_generated_idea.title}</h4><p className="mt-3 mb-0 text-sm leading-6 text-zinc-400">{concept.ai_generated_idea.gameplay_loop}</p><dl className="mt-5 grid gap-4 text-sm"><div><dt className="text-zinc-600">Mechanics</dt><dd className="mt-1 text-zinc-300">{concept.ai_generated_idea.mechanics.join(" · ")}</dd></div><div><dt className="text-zinc-600">Target player</dt><dd className="mt-1 text-zinc-300">{concept.ai_generated_idea.target_player}</dd></div><div><dt className="text-zinc-600">Price range</dt><dd className="mt-1 text-zinc-300">{concept.ai_generated_idea.steam_price_range}</dd></div></dl></div></div> : null}
          </Card>
        </section>
      </div>
    </div>
  );
}

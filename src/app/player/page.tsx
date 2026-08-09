"use client";

import { FormEvent, useState } from "react";

import { GameCard } from "@/components/game-card";
import { Card } from "@/components/ui/card";
import { analyzePlayer, ApiError } from "@/lib/api/client";
import type { PlayerRecommendation } from "@/lib/api/types";

const INITIAL_VISIBLE_DISCOVERY = 12;
const DISCOVERY_PAGE_SIZE = 100;
const MAX_DISCOVERY_RECOMMENDATIONS = 400;

export default function PlayerPage() {
  const [profileUrl, setProfileUrl] = useState("");
  const [steamKey, setSteamKey] = useState("");
  const [recommendations, setRecommendations] = useState<PlayerRecommendation[]>([]);
  const [status, setStatus] = useState("Enter a public Steam profile to analyze your fit.");
  const [loading, setLoading] = useState(false);
  const [hasAnalyzed, setHasAnalyzed] = useState(false);
  const [genreFilter, setGenreFilter] = useState("all");
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE_DISCOVERY);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [hasMorePages, setHasMorePages] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<"public" | "keyed">("public");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const mode = submitter?.value ?? "public";
    const requestKey = mode === "keyed" ? steamKey.trim() || undefined : undefined;
    setLoading(true);
    setStatus("Analyzing cached GamePulse signals…");
    try {
      const response = await analyzePlayer(profileUrl.trim(), requestKey, 0);
      setRecommendations(response.recommendations);
      window.sessionStorage.setItem("gamepulse.player-owned-games", JSON.stringify(response.recommendations.filter((item) => item.owned === true).map((item) => ({ steamAppId: item.steam_app_id, name: item.name, genres: item.genres ?? [] }))));
      setGenreFilter("all");
      setVisibleCount(INITIAL_VISIBLE_DISCOVERY);
      setHasAnalyzed(true);
      setAnalysisMode(mode === "keyed" ? "keyed" : "public");
      setNextPage(response.paging?.next_page ?? null);
      setHasMorePages(response.paging?.has_more ?? false);
      setStatus(`${response.source_name} · ${response.recommendations.length} recommendations ranked for this session.`);
    } catch (error) {
      setRecommendations([]);
      setHasAnalyzed(false);
      setStatus(error instanceof ApiError ? error.message : "The profile could not be analyzed right now. Check the URL and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function loadMore() {
    if (nextPage === null || loadingMore || discoveryRecommendations.length >= MAX_DISCOVERY_RECOMMENDATIONS) return;
    setLoadingMore(true);
    setStatus("Loading another bounded page; Steam library access is repeated for this request only…");
    try {
      const requestKey = analysisMode === "keyed" ? steamKey.trim() || undefined : undefined;
      const response = await analyzePlayer(profileUrl.trim(), requestKey, nextPage);
      setRecommendations((current) => {
        const byId = new Map(current.map((item) => [item.steam_app_id, item]));
        for (const item of response.recommendations) byId.set(item.steam_app_id, item);
        const unique = Array.from(byId.values());
        const owned = unique.filter((item) => item.owned === true);
        const discovery = unique.filter((item) => item.owned !== true).slice(0, MAX_DISCOVERY_RECOMMENDATIONS);
        return [...owned, ...discovery];
      });
      setNextPage(response.paging?.next_page ?? null);
      setHasMorePages(response.paging?.has_more ?? false);
      setVisibleCount((count) => Math.min(MAX_DISCOVERY_RECOMMENDATIONS, count + DISCOVERY_PAGE_SIZE));
      setStatus(`${response.source_name} · more recommendations loaded for this session.`);
    } catch (error) {
      setStatus(error instanceof ApiError ? error.message : "More recommendations could not be loaded right now.");
    } finally {
      setLoadingMore(false);
    }
  }

  const discoveryRecommendations = recommendations.filter((item) => item.owned !== true);
  const genres = Array.from(new Set(discoveryRecommendations.flatMap((item) => [...(item.genres ?? []), ...(item.tags ?? [])]))).filter((value) => value.trim().toLowerCase() !== "video production").sort((a, b) => a.localeCompare(b));
  const filteredRecommendations = genreFilter === "all"
    ? discoveryRecommendations
    : discoveryRecommendations.filter((item) => [...(item.genres ?? []), ...(item.tags ?? [])].includes(genreFilter));
  const visibleRecommendations = filteredRecommendations.slice(0, visibleCount);

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
              <p className="mt-2 mb-0 text-xs leading-5 text-zinc-600">Public-profile mode sends no key and requires the profile&apos;s games to be visible publicly. A key, if supplied, is used for this request only. Load more checks the Steam library again for each page; no library or key is stored.</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <button type="submit" name="analysis-mode" value="public" disabled={loading} className="min-h-12 rounded-xl bg-violet-500 px-5 text-sm font-semibold text-white transition hover:bg-violet-400 disabled:cursor-wait disabled:opacity-60">{loading ? "Analyzing…" : "Analyze without a key"}</button>
              <button type="submit" name="analysis-mode" value="keyed" disabled={loading} className="min-h-12 rounded-xl border border-white/10 bg-white/[0.04] px-5 text-sm font-semibold text-zinc-200 transition hover:border-violet-400/40 hover:bg-white/[0.07] disabled:cursor-wait disabled:opacity-60">Analyze with optional Web API key</button>
            </div>
          </form>
          <p className="mt-5 mb-0 text-sm leading-6 text-zinc-500" aria-live="polite">{status}</p>
        </Card>
      </section>

      {discoveryRecommendations.length ? (
        <section className="mt-14" aria-labelledby="player-results-title">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 id="player-results-title" className="m-0 text-2xl font-semibold tracking-[-0.035em] text-white">Recommendations</h2>
              <p className="mt-2 mb-0 text-sm text-zinc-500">Neon catalog games · personal fit 45% · reviews 20% · activity 15% · momentum 20%</p>
            </div>
            <div>
              <label htmlFor="player-genre-filter" className="text-sm font-semibold text-zinc-300">Filter recommendations by Steam tag or genre</label>
              <select id="player-genre-filter" value={genreFilter} onChange={(event) => { setGenreFilter(event.target.value); setVisibleCount(INITIAL_VISIBLE_DISCOVERY); }} className="mt-2 min-h-11 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-white outline-none focus:border-violet-400/70">
                <option value="all">All types</option>
                {genres.map((genre) => <option key={genre} value={genre}>{genre}</option>)}
              </select>
            </div>
          </div>
          <div className="mt-7 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {visibleRecommendations.map((item) => (
              <GameCard key={item.steam_app_id} steamAppId={item.steam_app_id} name={item.name} headerImageUrl={item.header_image_url} primaryScore={item.score} supportingMetrics={[{ label: "Reviews", value: item.review_score === null ? "—" : `${Math.round((item.review_score <= 1 ? item.review_score * 100 : item.review_score))}%` }, { label: item.current_players !== null ? "Players" : "Peak CCU", value: (item.current_players ?? item.peak_ccu) === null || (item.current_players ?? item.peak_ccu) === undefined ? "—" : (item.current_players ?? item.peak_ccu)!.toLocaleString() }]} reason={item.explanation} href={`/games/${item.steam_app_id}?from=player`} />
            ))}
          </div>
          {visibleCount < filteredRecommendations.length ? <button type="button" onClick={() => setVisibleCount((count) => count + INITIAL_VISIBLE_DISCOVERY)} className="mt-7 min-h-11 rounded-xl border border-white/10 bg-white/[0.04] px-5 text-sm font-semibold text-zinc-200 transition hover:border-violet-400/40 hover:bg-white/[0.07]">Show more</button> : null}
          {hasMorePages && nextPage !== null && discoveryRecommendations.length < MAX_DISCOVERY_RECOMMENDATIONS ? <button type="button" onClick={loadMore} disabled={loadingMore} className="mt-7 ml-3 min-h-11 rounded-xl bg-violet-500 px-5 text-sm font-semibold text-white transition hover:bg-violet-400 disabled:cursor-wait disabled:opacity-60">{loadingMore ? "Loading…" : "Load more recommendations"}</button> : null}
          {hasAnalyzed && !hasMorePages && discoveryRecommendations.length ? <p className="mt-4 mb-0 text-sm text-zinc-600">You&apos;re seeing all available recommendation pages for this session.</p> : null}
        </section>
      ) : null}
      {hasAnalyzed && !discoveryRecommendations.length ? (
        <Card className="mt-14 max-w-3xl p-6">
          <p className="m-0 text-sm font-medium text-zinc-300">No recommendations matched this profile yet.</p>
          <p className="mt-2 mb-0 text-sm leading-6 text-zinc-600">Try another public profile or check back after more GamePulse signals are cached.</p>
        </Card>
      ) : null}
    </div>
  );
}

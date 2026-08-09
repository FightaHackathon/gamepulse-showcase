import { notFound } from "next/navigation";

import { GameDetailHero } from "@/components/game-detail/hero";
import { KeyMetrics } from "@/components/game-detail/key-metrics";
import { MarketPosition } from "@/components/game-detail/market-position";
import { PlayerActivity } from "@/components/game-detail/player-activity";
import { PlayerOriginContext } from "@/components/game-detail/player-origin-context";
import { ReviewBreakdown } from "@/components/game-detail/review-breakdown";
import { StreamingTrend } from "@/components/game-detail/streaming-trend";
import { ApiError, getGame, getGameHistory } from "@/lib/api/client";
import type { MetricValue } from "@/lib/api/types";

async function historyOrEmpty(appId: number, metric: string): Promise<MetricValue[]> {
  try {
    return await getGameHistory(appId, metric);
  } catch {
    return [];
  }
}

function latestMetric(metrics: MetricValue[], metric: string) {
  return metrics.find(
    (item) => item.metric === metric && item.value_numeric !== null && Number.isFinite(item.value_numeric),
  );
}

export default async function GameDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ steamAppId: string }>;
  searchParams: Promise<{ from?: string }>;
}) {
  const { steamAppId } = await params;
  const { from } = await searchParams;
  const fromPlayer = from === "player";
  const appId = Number(steamAppId);
  if (!Number.isInteger(appId) || appId <= 0) notFound();

  let game;
  let liveRefreshFallback = false;
  try {
    game = await getGame(appId, true);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    try {
      game = await getGame(appId, false);
      liveRefreshFallback = true;
    } catch {
      throw error;
    }
  }

  const [currentPlayerHistory, peakPlayerHistory, streamingHistory] = await Promise.all([
    historyOrEmpty(appId, "current_players"),
    historyOrEmpty(appId, "peak_ccu"),
    historyOrEmpty(appId, "average_viewers_30d"),
  ]);
  const currentPlayerMetric = latestMetric(game.metrics, "current_players");
  const hasCurrentPlayerMetric = currentPlayerMetric?.value_numeric !== null && currentPlayerMetric !== undefined;
  const playerHistory = currentPlayerHistory.length >= 2
    ? currentPlayerHistory
    : peakPlayerHistory.length >= 2
      ? peakPlayerHistory
      : currentPlayerHistory.length
        ? currentPlayerHistory
        : peakPlayerHistory;
  const playerFallback = currentPlayerMetric ?? latestMetric(game.metrics, "peak_ccu");
  const streamingFallback = latestMetric(game.metrics, "average_viewers_30d");
  const refreshMessage = game.refresh_status === "success"
    ? "Selected-game Steam and streaming snapshots refreshed just now."
    : game.refresh_status === "partial_success"
      ? "Some selected-game snapshots refreshed; unavailable providers use the latest cached evidence."
      : game.refresh_status === "failure"
        ? "Live selected-game refresh was unavailable; showing the latest cached evidence."
        : liveRefreshFallback
          ? "Live refresh was unavailable; showing the latest Neon catalog and cached evidence."
          : null;

  return (
    <div className="gp-page py-2 lg:py-4">
      <GameDetailHero game={game} />
      <KeyMetrics game={game} includeStreaming={!fromPlayer} />
      {fromPlayer ? <PlayerOriginContext genres={game.genres} /> : null}
      {refreshMessage ? <p role="status" className="mt-5 mb-0 text-sm text-zinc-500">{refreshMessage}</p> : null}

      <PlayerActivity points={playerHistory} fallbackPoint={playerFallback} />
      {!fromPlayer ? <StreamingTrend points={streamingHistory} fallbackPoint={streamingFallback} /> : null}
      <ReviewBreakdown game={game} />
      {!fromPlayer ? <MarketPosition game={game} /> : null}
    </div>
  );
}

import { notFound } from "next/navigation";

import { GameDetailHero } from "@/components/game-detail/hero";
import { KeyMetrics } from "@/components/game-detail/key-metrics";
import { MarketPosition } from "@/components/game-detail/market-position";
import { PlayerActivity } from "@/components/game-detail/player-activity";
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

export default async function GameDetailPage({
  params,
}: {
  params: Promise<{ steamAppId: string }>;
}) {
  const { steamAppId } = await params;
  const appId = Number(steamAppId);
  if (!Number.isInteger(appId) || appId <= 0) notFound();

  let game;
  try {
    game = await getGame(appId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const [playerHistory, streamingHistory] = await Promise.all([
    historyOrEmpty(appId, "current_players"),
    historyOrEmpty(appId, "average_viewers_30d"),
  ]);

  return (
    <div className="gp-page py-2 lg:py-4">
      <GameDetailHero game={game} />
      <KeyMetrics game={game} />

      <PlayerActivity points={playerHistory} />
      <StreamingTrend points={streamingHistory} />
      <ReviewBreakdown game={game} />
      <MarketPosition game={game} />
    </div>
  );
}

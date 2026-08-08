import { notFound } from "next/navigation";

import { GameDetailHero } from "@/components/game-detail/hero";
import { KeyMetrics } from "@/components/game-detail/key-metrics";
import { ApiError, getGame } from "@/lib/api/client";

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

  return (
    <div className="gp-page py-2 lg:py-4">
      <GameDetailHero game={game} />
      <KeyMetrics game={game} />
    </div>
  );
}

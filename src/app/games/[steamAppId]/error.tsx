"use client";

export default function GameDetailError({ reset }: { reset: () => void }) {
  return (
    <div className="gp-page grid min-h-[70dvh] place-items-center py-12 text-center">
      <div className="max-w-lg">
        <h1 className="m-0 text-3xl font-semibold tracking-[-0.04em] text-white">Game details are temporarily unavailable</h1>
        <p className="mt-3 mb-0 leading-7 text-zinc-500">
          GamePulse could not read the cached data for this game. Your other workspaces are still available.
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-7 min-h-10 rounded-xl bg-violet-500 px-4 text-sm font-semibold text-white transition hover:bg-violet-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300"
        >
          Try again
        </button>
      </div>
    </div>
  );
}

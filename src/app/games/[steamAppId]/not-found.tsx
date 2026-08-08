import Link from "next/link";

export default function GameNotFound() {
  return (
    <div className="gp-page grid min-h-[70dvh] place-items-center py-12 text-center">
      <div className="max-w-md">
        <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-violet-500/10 text-sm font-black tracking-[0.18em] text-violet-300">
          GP
        </div>
        <h1 className="mt-6 mb-0 text-3xl font-semibold tracking-[-0.04em] text-white">Game not found</h1>
        <p className="mt-3 mb-0 leading-7 text-zinc-500">
          GamePulse does not have a cached Steam record for this App ID yet.
        </p>
        <Link
          href="/"
          className="mt-7 inline-flex min-h-10 items-center rounded-xl border border-white/10 bg-white/[0.05] px-4 text-sm font-semibold text-zinc-200 transition hover:bg-white/[0.09] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400"
        >
          Back to GamePulse
        </Link>
      </div>
    </div>
  );
}

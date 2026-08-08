import { ModeCard } from "@/components/mode-card";

const modes = [
  {
    title: "Player",
    description: "Find what to play",
    detail: "Rank games from your Steam library or discover something new with explainable recommendations.",
    href: "/player",
    iconName: "player" as const,
  },
  {
    title: "Streamer",
    description: "Find what to stream",
    detail: "Simulate a zero-audience channel and compare games by discoverability, audience potential, or balanced growth.",
    href: "/streamer",
    iconName: "streamer" as const,
  },
  {
    title: "Developer",
    description: "Find what to build",
    detail: "Explore evidence-backed Steam opportunities, then turn promising market directions into a focused game brief.",
    href: "/developer",
    iconName: "developer" as const,
  },
];

export default function HomePage() {
  return (
    <div className="gp-page flex min-h-[calc(100dvh-5.5rem)] flex-col justify-center py-10 lg:py-14">
      <div className="max-w-[760px]">
        <h1 className="gp-title">GamePulse</h1>
        <p className="gp-subtitle mt-6 mb-0">
          Steam/PC intelligence for one clear decision at a time. Choose the workspace that matches what you want to do next.
        </p>
      </div>

      <section aria-label="GamePulse modes" className="mt-12 grid grid-cols-1 gap-4 md:grid-cols-3 lg:mt-16">
        {modes.map((mode) => (
          <ModeCard key={mode.href} {...mode} />
        ))}
      </section>
    </div>
  );
}

import { Gamepad2, Hammer, Radio } from "lucide-react";

const workspaces = [
  {
    title: "Player",
    description: "Ranks games you already own and helps discover new Steam games with explainable recommendation factors.",
    Icon: Gamepad2,
  },
  {
    title: "Streamer",
    description: "Simulates a zero-audience channel and compares category opportunities without requiring an established Twitch account.",
    Icon: Radio,
  },
  {
    title: "Developer",
    description: "Turns cached Steam and streaming signals into market opportunities, then into clearly separated generated game directions.",
    Icon: Hammer,
  },
];

export default function AboutPage() {
  return (
    <div className="gp-page py-3 lg:py-8">
      <div className="max-w-3xl">
        <h1 className="m-0 text-[clamp(2.2rem,5vw,3.8rem)] font-semibold tracking-[-0.055em] text-white">About GamePulse</h1>
        <p className="mt-5 mb-0 text-base leading-7 text-zinc-500">
          GamePulse is a Steam/PC decision tool built around three separate questions: what should I play, what should I stream, and what could I build next?
        </p>
      </div>

      <section className="mt-12 grid gap-4 md:grid-cols-3" aria-label="GamePulse workspaces">
        {workspaces.map(({ title, description, Icon }) => (
          <div key={title} className="border-t border-white/[0.08] pt-5">
            <Icon aria-hidden="true" className="size-5 text-violet-300" />
            <h2 className="mt-5 mb-0 text-lg font-semibold tracking-[-0.025em] text-white">{title}</h2>
            <p className="mt-2 mb-0 text-sm leading-6 text-zinc-500">{description}</p>
          </div>
        ))}
      </section>

      <section className="mt-14 max-w-3xl border-t border-white/[0.07] pt-9">
        <h2 className="m-0 text-xl font-semibold tracking-[-0.025em] text-white">How to read the data</h2>
        <div className="mt-5 space-y-4 text-sm leading-7 text-zinc-500">
          <p className="m-0">GamePulse keeps source, observation time, freshness and confidence alongside external metrics so estimates are distinguishable from direct observations.</p>
          <p className="m-0">SteamSpy ownership ranges are third-party estimates. They are not verified sales, revenue, downloads, or units sold.</p>
          <p className="m-0">Generated Developer concepts are suggestions built from market evidence; the generated mechanics or creative direction are not themselves market facts.</p>
        </div>
      </section>
    </div>
  );
}

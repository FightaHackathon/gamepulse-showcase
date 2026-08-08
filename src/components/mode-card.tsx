import { ArrowUpRight, Gamepad2, Hammer, Radio } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";

const icons = {
  player: Gamepad2,
  streamer: Radio,
  developer: Hammer,
} as const;

export type ModeCardProps = {
  title: string;
  description: string;
  detail: string;
  href: string;
  iconName: keyof typeof icons;
};

export function ModeCard({ title, description, detail, href, iconName }: ModeCardProps) {
  const Icon = icons[iconName];

  return (
    <Link
      data-testid="mode-card"
      href={href}
      className="group block rounded-[1.35rem] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/80"
    >
      <Card
        className={cn(
          "flex min-h-[252px] flex-col p-6 transition duration-200",
          "hover:-translate-y-1 hover:border-violet-400/25 hover:bg-white/[0.052] hover:shadow-[0_24px_72px_rgba(0,0,0,0.34)]",
        )}
      >
        <div className="mb-auto flex items-start justify-between gap-4">
          <div className="grid size-11 place-items-center rounded-2xl border border-violet-400/15 bg-violet-500/10 text-violet-300">
            <Icon aria-hidden="true" className="size-5 stroke-[1.7]" />
          </div>
          <ArrowUpRight
            aria-hidden="true"
            className="size-5 text-zinc-600 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-violet-300"
          />
        </div>

        <div className="mt-10">
          <h2 className="m-0 text-[1.35rem] font-semibold tracking-[-0.025em] text-white">{title}</h2>
          <p className="mt-2 mb-0 text-base font-medium text-zinc-300">{description}</p>
          <p className="mt-3 mb-0 max-w-[28rem] text-sm leading-6 text-zinc-500">{detail}</p>
        </div>
      </Card>
    </Link>
  );
}

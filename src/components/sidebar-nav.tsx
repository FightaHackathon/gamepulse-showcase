import {
  Gamepad2,
  Hammer,
  Home,
  Info,
  Radio,
  Settings,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

const navigation: Array<{ label: string; href: string; icon: LucideIcon }> = [
  { label: "Home", href: "/", icon: Home },
  { label: "Player", href: "/player", icon: Gamepad2 },
  { label: "Streamer", href: "/streamer", icon: Radio },
  { label: "Developer", href: "/developer", icon: Hammer },
  { label: "Settings", href: "/settings", icon: Settings },
  { label: "About", href: "/about", icon: Info },
];

export function SidebarNav() {
  return (
    <nav aria-label="Primary" className="flex min-w-0 flex-col gap-1.5 max-[860px]:flex-row max-[860px]:overflow-x-auto">
      {navigation.map(({ label, href, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className="group flex min-h-10 items-center gap-3 rounded-xl px-3 text-sm font-medium text-zinc-400 transition hover:bg-white/[0.055] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/80 max-[860px]:shrink-0"
        >
          <Icon aria-hidden="true" className="size-[17px] stroke-[1.8] text-zinc-500 transition group-hover:text-violet-300" />
          {label}
        </Link>
      ))}
    </nav>
  );
}

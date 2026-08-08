import type { ReactNode } from "react";

import { SidebarNav } from "./sidebar-nav";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-[var(--gp-bg)] text-zinc-100">
      <div className="mx-auto grid min-h-dvh w-full max-w-[1680px] grid-cols-[220px_minmax(0,1fr)] max-[860px]:grid-cols-1">
        <aside className="sticky top-0 flex h-dvh flex-col border-r border-white/[0.07] bg-[#0c0c12]/90 px-5 py-7 backdrop-blur-xl max-[860px]:static max-[860px]:h-auto max-[860px]:border-b max-[860px]:border-r-0 max-[860px]:px-4 max-[860px]:py-4">
          <div className="mb-9 flex items-center gap-3 px-2 max-[860px]:mb-4">
            <span aria-hidden="true" className="grid size-8 place-items-center rounded-xl bg-violet-500 text-sm font-black text-white shadow-[0_8px_28px_rgba(124,58,237,0.35)]">
              G
            </span>
            <span className="text-[0.82rem] font-black tracking-[0.2em] text-white">GAMEPULSE</span>
          </div>

          <SidebarNav />

          <p className="mt-auto px-3 pt-8 text-[0.68rem] leading-5 text-zinc-600 max-[860px]:hidden">
            Steam/PC intelligence with source-aware market signals.
          </p>
        </aside>

        <main className="min-w-0 px-8 py-8 sm:px-10 lg:px-14 lg:py-11 max-[640px]:px-5 max-[640px]:py-6">
          {children}
        </main>
      </div>
    </div>
  );
}

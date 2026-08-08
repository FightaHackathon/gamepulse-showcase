import { KeyRound, ShieldCheck } from "lucide-react";

import { SourceStatusList } from "@/components/source-status-list";
import { Card } from "@/components/ui/card";
import { getSourceStatus } from "@/lib/api/client";
import type { SourceStatus } from "@/lib/api/types";

export default async function SettingsPage() {
  let sources: SourceStatus[] = [];
  let statusUnavailable = false;

  try {
    sources = await getSourceStatus();
  } catch {
    statusUnavailable = true;
  }

  return (
    <div className="gp-page py-3 lg:py-8">
      <div className="max-w-2xl">
        <h1 className="m-0 text-[clamp(2.2rem,5vw,3.8rem)] font-semibold tracking-[-0.055em] text-white">Settings</h1>
        <p className="mt-4 mb-0 text-base leading-7 text-zinc-500">
          Check GamePulse data readiness and understand which optional features need a session-only credential.
        </p>
      </div>

      <section className="mt-12 max-w-4xl">
        <div className="mb-5">
          <h2 className="m-0 text-xl font-semibold tracking-[-0.025em] text-white">Data sources</h2>
          <p className="mt-2 mb-0 text-sm leading-6 text-zinc-600">
            Core market workspaces use cached server-side snapshots; one unavailable provider should not blank the application.
          </p>
        </div>
        {statusUnavailable ? (
          <Card className="p-6">
            <p className="m-0 text-sm font-medium text-zinc-300">Source status could not be loaded.</p>
            <p className="mt-2 mb-0 text-sm leading-6 text-zinc-600">Cached data may still be available inside individual GamePulse workspaces.</p>
          </Card>
        ) : (
          <SourceStatusList sources={sources} />
        )}
      </section>

      <section className="mt-12 max-w-4xl border-t border-white/[0.07] pt-10">
        <h2 className="m-0 text-xl font-semibold tracking-[-0.025em] text-white">Steam profile personalization</h2>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <Card className="p-5">
            <KeyRound aria-hidden="true" className="size-5 text-violet-300" />
            <h3 className="mt-5 mb-0 text-base font-semibold text-white">Optional in Player mode</h3>
            <p className="mt-2 mb-0 text-sm leading-6 text-zinc-500">
              A Steam Web API key can unlock profile-library personalization. The input itself belongs to the Player workspace.
            </p>
          </Card>
          <Card className="p-5">
            <ShieldCheck aria-hidden="true" className="size-5 text-violet-300" />
            <h3 className="mt-5 mb-0 text-base font-semibold text-white">Session only</h3>
            <p className="mt-2 mb-0 text-sm leading-6 text-zinc-500">
              GamePulse must not persist a visitor key to Postgres, localStorage, sessionStorage, cookies, logs, analytics, or committed files.
            </p>
          </Card>
        </div>
      </section>
    </div>
  );
}

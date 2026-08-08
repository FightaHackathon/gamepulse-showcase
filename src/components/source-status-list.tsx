import { AlertCircle, CheckCircle2, Clock3, MinusCircle } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { SourceStatus } from "@/lib/api/types";

function stateMeta(state: string) {
  switch (state) {
    case "healthy":
      return { label: "Ready", Icon: CheckCircle2, className: "text-emerald-300" };
    case "degraded":
      return { label: "Degraded", Icon: MinusCircle, className: "text-amber-300" };
    case "stale":
      return { label: "Stale", Icon: Clock3, className: "text-amber-300" };
    case "error":
      return { label: "Unavailable", Icon: AlertCircle, className: "text-rose-300" };
    default:
      return { label: state || "Unknown", Icon: MinusCircle, className: "text-zinc-400" };
  }
}

function formatTime(value: string | null) {
  if (!value) return "No successful refresh yet";
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return value;
  return `Last success ${new Date(parsed).toLocaleString("en", { dateStyle: "medium", timeStyle: "short" })}`;
}

export function SourceStatusList({ sources }: { sources: SourceStatus[] }) {
  if (!sources.length) {
    return (
      <Card className="p-6">
        <p className="m-0 text-sm font-medium text-zinc-300">Source status is not available yet.</p>
        <p className="mt-2 mb-0 text-sm leading-6 text-zinc-600">
          GamePulse can still render cached product surfaces once the database has been seeded.
        </p>
      </Card>
    );
  }

  return (
    <div className="overflow-hidden rounded-[1.35rem] border border-white/[0.075] bg-white/[0.025]">
      {sources.map((source, index) => {
        const { label, Icon, className } = stateMeta(source.state);
        return (
          <div
            key={source.provider_name}
            className={`grid gap-4 px-5 py-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center ${index ? "border-t border-white/[0.065]" : ""}`}
          >
            <div className="min-w-0">
              <div className="text-sm font-semibold text-zinc-100">{source.provider_name}</div>
              <div className="mt-1 text-xs leading-5 text-zinc-600">{formatTime(source.latest_success_at)}</div>
              {source.last_error ? (
                <div className="mt-2 line-clamp-2 text-xs leading-5 text-rose-300/70">{source.last_error}</div>
              ) : null}
            </div>
            <div className={`flex items-center gap-2 text-xs font-semibold ${className}`}>
              <Icon aria-hidden="true" className="size-4 stroke-[1.8]" />
              {label}
            </div>
          </div>
        );
      })}
    </div>
  );
}

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

function relativeTime(observedAt: string, now: number) {
  const observed = Date.parse(observedAt);
  if (!Number.isFinite(observed)) return "unknown age";
  const seconds = Math.max(0, Math.floor((now - observed) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function SourceMeta({
  sourceName,
  observedAt,
  confidence,
  now = Date.now(),
  className,
}: {
  sourceName: string;
  observedAt: string;
  confidence: string;
  now?: number;
  className?: string;
}) {
  const absolute = Number.isFinite(Date.parse(observedAt))
    ? new Date(observedAt).toLocaleString("en", { dateStyle: "medium", timeStyle: "short" })
    : observedAt;

  return (
    <div className={cn("flex flex-wrap items-center gap-2 text-xs text-zinc-500", className)}>
      <span>{sourceName}</span>
      <span aria-hidden="true" className="text-zinc-700">•</span>
      <time dateTime={observedAt} title={absolute}>
        {relativeTime(observedAt, now)}
      </time>
      <Badge className="border-white/[0.07] bg-transparent px-2 py-0.5 text-[0.66rem] text-zinc-500">
        {confidence}
      </Badge>
    </div>
  );
}

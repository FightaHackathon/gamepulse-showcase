import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-xl bg-white/[0.07]", className)}
      {...props}
    />
  );
}

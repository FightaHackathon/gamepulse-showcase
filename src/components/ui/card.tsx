import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-[1.35rem] border border-white/8 bg-white/[0.035] shadow-[0_18px_60px_rgba(0,0,0,0.22)]",
        className,
      )}
      {...props}
    />
  );
}

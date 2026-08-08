import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
};

export function Button({ className, variant = "primary", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex min-h-10 items-center justify-center rounded-xl px-4 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/80 disabled:pointer-events-none disabled:opacity-50",
        variant === "primary" &&
          "bg-violet-500 text-white shadow-[0_10px_32px_rgba(124,58,237,0.28)] hover:bg-violet-400",
        variant === "secondary" &&
          "border border-white/10 bg-white/[0.055] text-zinc-100 hover:bg-white/[0.09]",
        variant === "ghost" && "text-zinc-300 hover:bg-white/[0.06] hover:text-white",
        className,
      )}
      {...props}
    />
  );
}

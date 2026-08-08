"use client";

import Image from "next/image";
import { useState } from "react";

import { cn } from "@/lib/cn";

export function GameImage({
  src,
  alt,
  className,
  sizes = "(max-width: 768px) 100vw, 33vw",
  priority = false,
}: {
  src: string | null;
  alt: string;
  className?: string;
  sizes?: string;
  priority?: boolean;
}) {
  const [failed, setFailed] = useState(!src);

  if (!src || failed) {
    return (
      <div
        data-testid="game-image-fallback"
        role="img"
        aria-label={`${alt} artwork unavailable`}
        className={cn(
          "grid h-full w-full place-items-center bg-[radial-gradient(circle_at_30%_25%,rgba(139,92,246,0.28),transparent_42%),linear-gradient(145deg,#171723,#0d0d13)]",
          className,
        )}
      >
        <span className="text-xs font-black tracking-[0.28em] text-white/35">GAMEPULSE</span>
      </div>
    );
  }

  return (
    <Image
      fill
      src={src}
      alt={alt}
      sizes={sizes}
      priority={priority}
      onError={() => setFailed(true)}
      className={cn("object-cover", className)}
    />
  );
}

import type { Metadata } from "next";
import Script from "next/script";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { HYDRATION_ATTRIBUTE_SANITIZER_SCRIPT } from "@/lib/hydration-attribute-sanitizer";

import "./globals.css";

export const metadata: Metadata = {
  title: "GamePulse",
  description: "Steam/PC intelligence for players, streamers, and game developers.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <Script
          id="hydration-attribute-sanitizer"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: HYDRATION_ATTRIBUTE_SANITIZER_SCRIPT }}
        />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

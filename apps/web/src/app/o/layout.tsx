import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { atkinson, fraunces, plexMono } from "@/theme/fonts";

import "../globals.css";

// The doctor page has its own root layout: light face, no locale segment, no app providers, so
// its JavaScript stays small (design §11, §16). The token is in the fragment, never on the server.
export const metadata: Metadata = {
  title: "Janus",
  referrer: "no-referrer",
  robots: { index: false },
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function DoctorLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={[atkinson.variable, fraunces.variable, plexMono.variable].join(
        " ",
      )}
      data-theme-style="two-faces"
      data-face="light"
      data-large-text="off"
      data-reduce-transparency="off"
    >
      <body className="antialiased">{children}</body>
    </html>
  );
}

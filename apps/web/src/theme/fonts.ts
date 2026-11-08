/**
 * Self-hosted fonts (DP2; OFL 1.1, files and licences in src/fonts). No third-party font request
 * (Req 23.4). `display: "swap"` so no web font blocks the first render (§16).
 */
import localFont from "next/font/local";

export const fraunces = localFont({
  src: [
    {
      path: "../fonts/Fraunces-SemiBold.woff2",
      weight: "600",
      style: "normal",
    },
  ],
  variable: "--font-fraunces",
  display: "swap",
  preload: false,
});

export const atkinson = localFont({
  src: [
    {
      path: "../fonts/AtkinsonHyperlegibleNext-Regular.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "../fonts/AtkinsonHyperlegibleNext-Bold.woff2",
      weight: "700",
      style: "normal",
    },
  ],
  variable: "--font-atkinson",
  display: "swap",
});

export const plexMono = localFont({
  src: [
    {
      path: "../fonts/IBMPlexMono-Regular.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "../fonts/IBMPlexMono-Medium.woff2",
      weight: "500",
      style: "normal",
    },
  ],
  variable: "--font-plex-mono",
  display: "swap",
  preload: false,
});

export const figtree = localFont({
  src: [
    {
      path: "../fonts/Figtree-Variable.woff2",
      weight: "300 900",
      style: "normal",
    },
  ],
  variable: "--font-figtree",
  display: "swap",
  preload: false,
});

export const fontVariables = [fraunces, atkinson, plexMono, figtree]
  .map((f) => f.variable)
  .join(" ");

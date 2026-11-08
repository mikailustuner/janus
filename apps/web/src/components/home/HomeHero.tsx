"use client";
/**
 * The home hero (Req 27.6, DP45, DP46): the Night Pharmacy scenes or the Glass Janus scene,
 * by theme. Both are server-rendered and CSS shows only the active theme's (the theme is set on
 * <html> before the first paint), so there is no flash and no layout shift; after hydration the
 * inactive hero is dropped, and only the active one loads its motion chunk. The page (a server component) preloads only the active theme's first image.
 * Swap the art here without touching the rest of the home page. Contract: the h1 of the hero,
 * `Home.intro`, the demo link first; Night Pharmacy ghosts are functional (each opens a demo
 * finding), decorative art is `aria-hidden`.
 */
import { useSettings } from "@/store/hooks";
import { useTheme } from "@/theme/words";

import { GlassJanusHero } from "./GlassJanusHero";
import { NightPharmacyHero } from "./NightPharmacyHero";

export function HomeHero() {
  const theme = useTheme();
  const { ready } = useSettings();
  // Same slots before and after hydration, so the kept hero is not remounted.
  return (
    <>
      {!ready || theme !== "glass" ? (
        <NightPharmacyHero active={ready && theme !== "glass"} />
      ) : null}
      {!ready || theme === "glass" ? (
        <GlassJanusHero active={ready && theme === "glass"} />
      ) : null}
    </>
  );
}

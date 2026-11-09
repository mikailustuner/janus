"use client";
/**
 * Home (design §3, §9; Req 27): the website's front page. The emergency notice first, then the
 * hero with the product sentence and "Try the demo" as the main action, how it works in three
 * steps, the regions and languages, and privacy in one sentence. The disclaimer is in the shell
 * footer of every page. The hero is the theme's scene (HomeHero, DP46); Glass Janus has its own
 * sections after it (GlassHomeSections, Clinical White, DP71).
 */
import { useEffect, useRef } from "react";

import { EmergencyNotice } from "@/components/EmergencyNotice";
import { ReminderCard } from "@/components/loop/ReminderCard";
import { ButtonLink, Card, SectionTitle } from "@/components/ui";
import { ZombieAlertCard } from "@/components/zombie/Zombie";
import { useDemo } from "@/demo/session";
import { localeNames, routing } from "@/i18n/routing";
import { useList, useSettings } from "@/store/hooks";
import { useT, useTheme } from "@/theme/words";

import { GlassHomeSections } from "./GlassHomeSections";
import { HomeHero } from "./HomeHero";

import { PATTERNS } from "./patterns";

export { PATTERNS };

export function Home() {
  const t = useT();
  const { ready, value } = useList();
  const demo = useDemo();
  const theme = useTheme();
  const settings = useSettings();
  // Both section sets are server-rendered and CSS shows the active theme's; after hydration the
  // inactive one is dropped (as HomeHero, DP71).
  const glass = settings.ready && theme === "glass";
  const night = settings.ready && theme !== "glass";
  const count = value.items.length;
  // The Glass hero's copy starts under the emergency bar, whatever its height (DP72).
  const bar = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = bar.current;
    if (!el) return;
    const root = document.documentElement;
    const ro = new ResizeObserver(() =>
      root.style.setProperty("--home-emergency-h", `${el.offsetHeight}px`),
    );
    ro.observe(el);
    return () => {
      ro.disconnect();
      root.style.removeProperty("--home-emergency-h");
    };
  }, []);
  const steps = [
    t("Home.how1"),
    t("Home.how2", { patterns: PATTERNS }),
    t("Home.how3"),
  ];
  return (
    <>
      {/* The home is full-bleed (DP46): the hero spans the window, the rest keeps the page width. */}
      {/* The emergency notice stays first on the first screen (Req 1.2), as a one-line bar over
          the top of the hero, under the header (DP46). */}
      <div className="relative">
        <div ref={bar} className="home-emergency">
          <EmergencyNotice slim />
        </div>
        <HomeHero />
      </div>
      <div className="mx-auto flex w-full max-w-[720px] flex-col gap-5 px-4 pt-5 lg:max-w-[1120px]">
        <ZombieAlertCard />
        <ReminderCard />
        {ready && count > 0 && !demo ? (
          <Card>
            <p className="font-bold">{t("Home.resume")}</p>
            <p className="text-muted">{t("Home.resumeCount", { count })}</p>
            <ButtonLink href="/medicines" className="self-start">
              {t("Medicines.title")}
            </ButtonLink>
          </Card>
        ) : null}
        {!glass ? (
          <div className="np-sections contents">
            <Card
              aria-labelledby="how"
              id="how-it-works"
              className="scroll-mt-24"
            >
              <SectionTitle id="how">{t("Home.howTitle")}</SectionTitle>
              <ol className="grid gap-4 md:grid-cols-3">
                {steps.map((s, i) => (
                  <li key={i} className="flex gap-3">
                    <span
                      aria-hidden
                      className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent font-bold text-on-accent"
                    >
                      {i + 1}
                    </span>
                    <span className="max-w-[40ch]">{s}</span>
                  </li>
                ))}
              </ol>
            </Card>
            <div className="grid gap-5 md:grid-cols-2">
              <Card aria-labelledby="coverage">
                <SectionTitle id="coverage">
                  {t("Home.coverageTitle")}
                </SectionTitle>
                <p>
                  <span className="font-bold">{t("Home.regions")}:</span>{" "}
                  {(["TR", "EU", "US"] as const)
                    .map((r) => t(`Common.region.${r}`))
                    .join(", ")}
                </p>
                <p>
                  <span className="font-bold">{t("Home.languages")}:</span>{" "}
                  {routing.locales.map((l, i) => (
                    <span key={l} lang={l}>
                      {i ? ", " : ""}
                      {localeNames[l]}
                    </span>
                  ))}
                </p>
              </Card>
              <Card aria-labelledby="home-privacy">
                <SectionTitle id="home-privacy">
                  {t("Home.privacy")}
                </SectionTitle>
                <p>{t("Home.privacyLine")}</p>
                <ButtonLink
                  href="/privacy"
                  variant="secondary"
                  className="self-start"
                >
                  {t("Shell.privacy")}
                </ButtonLink>
              </Card>
            </div>
          </div>
        ) : null}
        {!night ? <GlassHomeSections active={glass} /> : null}
      </div>
    </>
  );
}

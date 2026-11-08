"use client";
/**
 * Home (design §3, §9; Req 27): the website's front page. The emergency notice first, then the
 * hero with the product sentence and "Try the demo" as the main action, how it works in three
 * steps, the regions and languages, and privacy in one sentence. The disclaimer is in the shell
 * footer of every page. Two Faces shows the mask as the hero illustration: its two halves are the
 * links to the two faces. Glass shows the three colour fields.
 */
import { EmergencyNotice } from "@/components/EmergencyNotice";
import { ReminderCard } from "@/components/loop/ReminderCard";
import { ButtonLink, Card, SectionTitle } from "@/components/ui";
import { useDemo } from "@/demo/session";
import { localeNames, routing } from "@/i18n/routing";
import { useList } from "@/store/hooks";
import { useT } from "@/theme/words";

import { HomeHero } from "./HomeHero";

/** The number of published cascade patterns in the rule base (checked against the vocabulary). */
export const PATTERNS = 65;

export function Home() {
  const t = useT();
  const { ready, value } = useList();
  const demo = useDemo();
  const count = value.items.length;
  const steps = [
    t("Home.how1"),
    t("Home.how2", { patterns: PATTERNS }),
    t("Home.how3"),
  ];
  return (
    <>
      <EmergencyNotice />
      <ReminderCard />
      <HomeHero />
      {ready && count > 0 && !demo ? (
        <Card>
          <p className="font-bold">{t("Home.resume")}</p>
          <p className="text-muted">{t("Home.resumeCount", { count })}</p>
          <ButtonLink href="/medicines" className="self-start">
            {t("Medicines.title")}
          </ButtonLink>
        </Card>
      ) : null}
      <Card aria-labelledby="how">
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
          <SectionTitle id="coverage">{t("Home.coverageTitle")}</SectionTitle>
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
          <SectionTitle id="home-privacy">{t("Home.privacy")}</SectionTitle>
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
    </>
  );
}

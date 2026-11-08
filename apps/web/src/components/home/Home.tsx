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
import { Link } from "@/i18n/navigation";
import { localeNames, routing } from "@/i18n/routing";
import { useList } from "@/store/hooks";
import { useT, useTheme, useThemeWord } from "@/theme/words";

/** The number of published cascade patterns in the rule base (checked against the vocabulary). */
export const PATTERNS = 65;

const SHADOW = "var(--mask-shadow)";
const LIGHT = "var(--mask-light)";

/** One half of the mask (the left half; the right one is mirrored), with an eye hole. */
function MaskHalf({
  fill,
  stroke,
  mirror,
}: {
  fill: string;
  stroke: string;
  mirror?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 100 160"
      className="h-40 w-auto sm:h-52"
      aria-hidden
      focusable="false"
    >
      <g transform={mirror ? "translate(100 0) scale(-1 1)" : undefined}>
        <path
          fillRule="evenodd"
          style={{ fill, stroke }}
          strokeWidth="3"
          d="M100 8C44 8 6 36 6 80c0 42 44 72 94 72ZM60 62c-12 0-20 6-22 12 8 4 16 6 24 4 4-2 6-6 6-10 0-4-4-6-8-6Z"
        />
      </g>
    </svg>
  );
}

function MaskHero() {
  const w = useThemeWord();
  return (
    <nav aria-label={w("Shell.mask.label")} className="justify-self-center">
      <ul className="flex items-end">
        <li>
          <Link
            href="/start"
            className="flex flex-col items-center gap-2 rounded-l-[var(--radius-card)] p-2 font-bold no-underline"
          >
            <MaskHalf fill={SHADOW} stroke={LIGHT} />
            <span>{w("Shell.mask.patient")}</span>
          </Link>
        </li>
        <li>
          <Link
            href="/research"
            className="flex flex-col items-center gap-2 rounded-r-[var(--radius-card)] p-2 font-bold no-underline"
          >
            <MaskHalf fill={LIGHT} stroke={SHADOW} mirror />
            <span>{w("Shell.mask.research")}</span>
          </Link>
        </li>
      </ul>
    </nav>
  );
}

/** Glass: the three soft colour fields as the hero illustration (decorative). */
function Fields() {
  return (
    <div
      aria-hidden
      className="relative hidden h-64 overflow-hidden rounded-[var(--radius-card)] md:block"
    >
      <span className="absolute top-2 left-4 size-40 rounded-full bg-[var(--field-1)] blur-2xl" />
      <span className="absolute top-16 right-2 size-44 rounded-full bg-[var(--field-2)] blur-2xl" />
      <span className="absolute bottom-0 left-20 size-40 rounded-full bg-[var(--field-3)] blur-2xl" />
    </div>
  );
}

export function Home() {
  const t = useT();
  const w = useThemeWord();
  const theme = useTheme();
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
      <section
        aria-labelledby="home-title"
        className="grid items-center gap-6 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]"
      >
        <div className="flex flex-col gap-4">
          <p className="text-sm font-bold tracking-wide text-muted uppercase">
            {w("Home.tagline")}
          </p>
          <h1
            id="home-title"
            className="text-[length:var(--title-size)] leading-tight font-bold md:text-5xl"
          >
            {t("Home.title")}
          </h1>
          <p className="max-w-[60ch] text-lg">{t("Home.intro")}</p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <ButtonLink href="/demo">{t("Home.demo")}</ButtonLink>
            <ButtonLink href="/start" variant="secondary">
              {t("Home.start")}
            </ButtonLink>
          </div>
          <p className="text-sm text-muted">{t("Home.demoHint")}</p>
        </div>
        {theme === "two-faces" ? <MaskHero /> : <Fields />}
      </section>
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

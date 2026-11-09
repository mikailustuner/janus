"use client";
/**
 * The Glass Janus home sections, Clinical White (experience Req 31.5, 31.6, DP70, DP71): "At a
 * glance" (a bento grid), "How it works" with 3D icon chips, and privacy in one sentence. Every
 * figure is the recorded Istanbul demo or the rule base (`clinicalFacts.ts`, `patterns.ts`);
 * the mock-ups (phone screen, note paper, QR) are decorative and `aria-hidden`, each tile's
 * heading and sentence carry its meaning. Night Pharmacy keeps its own sections (Home.tsx).
 */
import { ButtonLink } from "@/components/ui";
import { localeNames, routing } from "@/i18n/routing";
import { useT } from "@/theme/words";

import { CheckIcon, DocIcon, LockIcon, ScanIcon, SearchIcon } from "../icons";

import { DEMO_FINDING } from "./clinicalFacts";
import { Capsule, useGlassMotion } from "./GlassJanusHero";
import { PATTERNS } from "./patterns";

/** Product sources by region (data-sources.md); proper names, not translated. */
const REGIONS = [
  { region: "TR", sources: "TİTCK" },
  { region: "EU", sources: "BDPM · CIMA" },
  { region: "US", sources: "openFDA" },
] as const;

/** A 7 × 7 QR-like mark for the note paper (decorative; the real QR is on the note). */
function QrMark() {
  return (
    <svg
      viewBox="0 0 7 7"
      width="56"
      height="56"
      className="gj-qr"
      shapeRendering="crispEdges"
      aria-hidden
      focusable="false"
    >
      <path
        className="fill-fg"
        d="M0 0h3v3H0zM4 0h3v3H4zM0 4h3v3H0zM4 4h1v1H4zM6 4h1v1H6zM5 5h1v1H5zM4 6h1v1H4zM6 6h1v1H6z"
      />
      <path className="fill-surface" d="M1 1h1v1H1zM5 1h1v1H5zM1 5h1v1H1z" />
    </svg>
  );
}

function PhoneMock() {
  const t = useT();
  return (
    <div className="gj-phone-stage" aria-hidden>
      <div className="gj-phone">
        <div className="gj-phone-screen">
          <p className="gj-phone-title">{t("Findings.title.glass")}</p>
          <p className="gj-phone-meta">{t("Demo.label")}</p>
          <div className="gj-phone-card">
            <p className="gj-phone-eyebrow">{t("Findings.kind.glass")}</p>
            <p className="gj-phone-pair">{t("Home.glass.cascadePair")}</p>
            <p className="gj-phone-meta">{t("Home.ghosts.pipc5")}</p>
          </div>
          <div className="gj-phone-tiles">
            <div className="gj-phone-tile">
              <p className="mono">
                {t("Home.glass.phoneMonths", {
                  months: DEMO_FINDING.monthsBetween,
                })}
              </p>
              <p className="gj-phone-meta">
                {t("Home.glass.phoneMonthsLabel")}
              </p>
            </div>
            <div className="gj-phone-tile">
              <p className="mono">{DEMO_FINDING.sources}</p>
              <p className="gj-phone-meta">
                {t("Cards.label.sources", { count: DEMO_FINDING.sources })}
              </p>
            </div>
          </div>
          <p className="gj-phone-button">{t("Findings.makeNote")}</p>
        </div>
      </div>
    </div>
  );
}

function NoteMock() {
  return (
    <div className="gj-note-stage" aria-hidden>
      <div className="gj-note">
        <div className="gj-note-back" />
        <div className="gj-note-paper">
          <span className="gj-note-line gj-note-head" />
          <span className="gj-note-line" style={{ width: "90%" }} />
          <span className="gj-note-line" style={{ width: "82%" }} />
          <span className="gj-note-line" style={{ width: "88%" }} />
          <span className="gj-note-line gj-note-accent" />
          <QrMark />
        </div>
      </div>
    </div>
  );
}

export function GlassHomeSections({ active }: { active: boolean }) {
  const t = useT();
  const root = useGlassMotion(active, false);
  const how = [
    { Icon: ScanIcon, title: "Home.glass.how1Title", text: t("Home.how1") },
    {
      Icon: SearchIcon,
      title: "Home.glass.how2Title",
      text: t("Home.how2", { patterns: PATTERNS }),
    },
    { Icon: DocIcon, title: "Home.glass.how3Title", text: t("Home.how3") },
  ] as const;
  return (
    <div className="gj-sections" data-testid="glass-sections">
      <section
        ref={root}
        className="gj-glance"
        aria-labelledby="gj-glance-title"
      >
        <p className="gj-kicker">{t("Home.glass.glanceEyebrow")}</p>
        <h2 id="gj-glance-title" className="gj-h2">
          {t("Home.glass.glanceTitle")}
        </h2>
        <div className="gj-bento">
          <div className="gj-tile gj-span-4 gj-tile-mint">
            <h3 className="gj-h3">{t("Home.glass.resultsTitle")}</h3>
            <p className="gj-tile-text">{t("Home.glass.resultsText")}</p>
            <PhoneMock />
            <div className="gj-tile-pill" aria-hidden>
              <Capsule
                cls="gj-pill-teal gj-spin-b"
                x={8}
                y={72}
                w={12}
                r={-24}
              />
            </div>
          </div>
          <div className="gj-tile gj-span-2 gj-tile-column">
            <h3 className="gj-h3">{t("Home.glass.noteTitle")}</h3>
            <p className="gj-tile-text">{t("Home.glass.noteText")}</p>
            <NoteMock />
          </div>
          <div className="gj-tile gj-span-2 gj-tile-dark">
            <p className="gj-dark-figure">
              <span className="gj-dark-big mono">{PATTERNS}</span>{" "}
              <span className="gj-dark-text">
                {t("Home.glass.patternsTile")}
              </span>
            </p>
            <div className="gj-ring" aria-hidden />
            <div className="gj-tile-pill" aria-hidden>
              <Capsule
                cls="gj-pill-navy gj-spin-c"
                x={62}
                y={70}
                w={26}
                r={30}
              />
            </div>
          </div>
          <div className="gj-tile gj-span-2">
            <h3 className="gj-h3">{t("Home.glass.regionsTitle")}</h3>
            <p className="gj-tile-text">{t("Home.glass.regionsText")}</p>
            <p className="gj-tile-langs">
              {routing.locales.map((l, i) => (
                <span key={l} lang={l}>
                  {i ? " · " : ""}
                  {localeNames[l]}
                </span>
              ))}
            </p>
            <ul className="gj-fan">
              {REGIONS.map(({ region, sources }) => (
                <li key={region} className="gj-fan-card">
                  <span className="font-bold">
                    {t(`Common.region.${region}`)}
                  </span>
                  <span className="gj-fan-source">{sources}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="gj-tile gj-span-2 gj-tile-warm">
            <h3 className="gj-h3">{t("Home.glass.sourcesTitle")}</h3>
            <p className="gj-tile-text">{t("Home.glass.sourcesText")}</p>
            <div className="gj-badge">
              <span className="gj-chip3d gj-chip3d-sm" aria-hidden>
                <CheckIcon size={20} className="text-accent" />
              </span>
              <p>
                <span className="block font-bold">
                  {t("Home.glass.badgeTitle")}
                </span>
                <span className="gj-tile-meta">
                  {t("Home.glass.badgeText")}
                </span>
              </p>
            </div>
          </div>
        </div>
      </section>

      <section
        id="gj-how"
        aria-labelledby="gj-how-title"
        className="gj-how scroll-mt-24"
      >
        <h2 id="gj-how-title" className="gj-h2">
          {t("Home.howTitle")}
        </h2>
        <ol className="gj-how-grid">
          {how.map(({ Icon, title, text }) => (
            <li key={title} className="gj-how-card">
              <span className="gj-chip3d" aria-hidden>
                <Icon size={24} className="text-accent" />
              </span>
              <h3 className="gj-how-title">{t(title)}</h3>
              <p className="gj-tile-text">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="gj-privacy" className="gj-privacy">
        <span className="gj-chip3d" aria-hidden>
          <LockIcon size={24} className="text-accent" />
        </span>
        <div className="flex min-w-0 flex-col gap-2">
          <h2 id="gj-privacy" className="gj-how-title">
            {t("Home.privacy")}
          </h2>
          <p className="gj-tile-text">{t("Home.privacyLine")}</p>
          <ButtonLink
            href="/privacy"
            variant="secondary"
            className="self-start"
          >
            {t("Shell.privacy")}
          </ButtonLink>
        </div>
      </section>
    </div>
  );
}

"use client";
/**
 * Glass Janus home, Clinical White (owner decision 2026-11-09; experience Req 31, DP68, DP69):
 * the clinical hero image full-bleed at its own aspect ratio (never cropped, nothing over the two
 * faces), the copy in ink on the light left area, two frosted tilted cards from the Istanbul demo
 * on the right, CSS-drawn capsules floating outside the faces and a slow light sweep. No ghosts,
 * no Halloween, nothing driven by scroll. Figures: `clinicalFacts.ts` (DP70).
 */
import { useEffect, useRef, type CSSProperties } from "react";

import { Link } from "@/i18n/navigation";
import { useT } from "@/theme/words";

import { ArrowRightIcon, LockIcon } from "../icons";

import { DEMO_FINDING } from "./clinicalFacts";
import { PATTERNS } from "./patterns";
import { ScenePicture } from "./ScenePicture";

/** Capsules in the free bands of the image (DP69): beside the head and on the floor. */
const PILLS = [
  { cls: "gj-pill-navy gj-spin-a", x: 61, y: 89, w: 4.6, r: -32 },
  { cls: "gj-pill-teal gj-spin-c gj-soft", x: 72, y: 25, w: 3.4, r: 38 },
  { cls: "gj-pill-amber gj-spin-b gj-softer", x: 38, y: 87, w: 7.2, r: 24 },
  { cls: "gj-pill-red gj-spin-a", x: 71.6, y: 80, w: 4.4, r: -18 },
] as const;

/** Starts the motion chunk (pause off-screen, pointer parallax) for an active Glass section. */
export function useGlassMotion(active: boolean, pointer: boolean) {
  const root = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = root.current;
    if (!el || !active) return;
    let stop: (() => void) | undefined;
    let cancelled = false;
    void import("./glassMotion").then(({ startGlassMotion }) => {
      if (!cancelled) stop = startGlassMotion(el, pointer);
    });
    return () => {
      cancelled = true;
      stop?.();
    };
  }, [active, pointer]);
  return root;
}

export function Capsule({
  cls,
  x,
  y,
  w,
  r,
}: {
  cls: string;
  x: number;
  y: number;
  w: number;
  r: number;
}) {
  return (
    <span
      className={`gj-pill-wrap ${cls}`}
      style={
        {
          left: `${x}%`,
          top: `${y}%`,
          width: `${w}%`,
          "--r": `${r}deg`,
        } as CSSProperties
      }
    >
      <span className="gj-pill" />
    </span>
  );
}

export function GlassJanusHero({ active }: { active: boolean }) {
  const t = useT();
  const root = useGlassMotion(active, true);
  return (
    <section
      ref={root}
      className="gj"
      aria-labelledby="gj-title"
      data-testid="glass-hero"
    >
      <div className="gj-media" data-testid="glass-hero-media">
        <ScenePicture
          name="clinical-hero"
          alt={t("Home.alt.glassHero")}
          className="gj-picture"
          first
        />
        <div className="gj-sweep" aria-hidden />
        <div className="gj-scrim" aria-hidden />
        <div className="gj-pills" aria-hidden>
          {PILLS.map((p, i) => (
            <Capsule key={i} {...p} />
          ))}
        </div>
      </div>
      <div className="gj-copy">
        <p className="gj-eyebrow">{t("Home.tagline.glass")}</p>
        <h1 id="gj-title" className="gj-title">
          {t("Home.glassHeadline")}
        </h1>
        <p className="gj-lead">{t("Home.intro")}</p>
        <div className="gj-actions">
          <Link href="/demo" className="gj-btn gj-btn-primary">
            {t("Home.demo")}
            <ArrowRightIcon size={18} />
          </Link>
          <a href="#gj-how" className="gj-btn">
            {t("Home.howTitle")}
          </a>
        </div>
        <p className="gj-hint">{t("Home.demoHint")}</p>
      </div>
      <div className="gj-cards" data-testid="glass-cards">
        <div
          className="gj-float gj-float-a"
          role="group"
          aria-label={t("Home.glass.cards")}
        >
          <div className="gj-card">
            <p className="gj-card-eyebrow">{t("Findings.kind.glass")}</p>
            <p className="gj-card-title">{t("Home.glass.cascadePair")}</p>
            <ul className="gj-card-chips">
              <li className="mono">
                {t("Home.glass.monthsApart", {
                  months: DEMO_FINDING.monthsBetween,
                })}
              </li>
              <li className="mono">
                {t("Home.glass.sources", { count: DEMO_FINDING.sources })}
              </li>
            </ul>
            <p className="gj-card-demo">{t("Demo.label")}</p>
          </div>
        </div>
        <div className="gj-float gj-float-b">
          <div className="gj-card gj-card-shift">
            <p className="gj-card-figure">
              <span className="gj-card-big mono">{PATTERNS}</span>{" "}
              <span>{t("Home.glass.patternsTile")}</span>
            </p>
            <p className="gj-card-foot">
              <LockIcon size={16} className="text-accent" />
              {t("Home.glass.photos")}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

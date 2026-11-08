"use client";
/**
 * Glass Janus home (steering design.md "Home scenes", Req 27.6, DP46): the glass two-faced mask
 * full-bleed, the headline and actions on the left over a scrim, a slow light sweep across the
 * glass, tiny floating capsule highlights and a subtle tilt on pointer move. No ghosts, no
 * Halloween.
 */
import { useEffect, useRef } from "react";

import { Link } from "@/i18n/navigation";
import { useT } from "@/theme/words";

import { ScenePicture } from "./ScenePicture";

const CAPSULES = [
  { x: 46, y: 38, d: 0 },
  { x: 55, y: 52, d: 1.6 },
  { x: 50, y: 64, d: 3.1 },
  { x: 58, y: 34, d: 4.4 },
  { x: 43, y: 56, d: 5.2 },
];

export function GlassJanusHero({ active }: { active: boolean }) {
  const t = useT();
  const root = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = root.current;
    if (!el || !active) return;
    let stop: (() => void) | undefined;
    let cancelled = false;
    void import("./glassMotion").then(({ startGlassMotion }) => {
      if (!cancelled) stop = startGlassMotion(el);
    });
    return () => {
      cancelled = true;
      stop?.();
    };
  }, [active]);
  return (
    <section
      ref={root}
      className="gj"
      aria-labelledby="gj-title"
      data-testid="glass-hero"
    >
      <div className="scene">
        <div className="scene-box gj-box">
          <ScenePicture name="glass-hero" alt={t("Home.alt.glassHero")} />
          <div className="gj-sweep" aria-hidden />
          {CAPSULES.map((c, i) => (
            <span
              key={i}
              className="gj-capsule"
              aria-hidden
              style={{
                left: `${c.x}%`,
                top: `${c.y}%`,
                animationDelay: `${c.d}s`,
              }}
            />
          ))}
        </div>
      </div>
      <div className="gj-copy">
        <div className="gj-copy-inner">
          <p className="scene-eyebrow">{t("Home.tagline.glass")}</p>
          <h1 id="gj-title" className="scene-title">
            {t("Home.glassHeadline")}
          </h1>
          <p className="scene-lead">{t("Home.intro")}</p>
          <div className="flex flex-wrap gap-3">
            <Link href="/demo" className="scene-btn scene-btn-primary">
              {t("Home.demo")}
            </Link>
            <a href="#how-it-works" className="scene-btn">
              {t("Home.howTitle")}
            </a>
          </div>
          <p className="scene-hint">{t("Home.demoHint")}</p>
        </div>
      </div>
    </section>
  );
}

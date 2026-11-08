"use client";
/**
 * Night Pharmacy home (steering design.md "Home scenes", experience Req 27.6, DP46). A pinned
 * stage scrubbed by scroll: the diorama with ghosts rising from the shop windows → the door
 * transition video → the medicine cabinet, where the ghosts line up as the Istanbul demo's
 * findings (each a button into the demo) and the glowing note becomes "Prepare the doctor note".
 * All text is real and translated; the images carry alt text, the video is decorative. The motion
 * (scrubbing, parallax, fireflies, the ghosts' lean) lives in `nightMotion.ts`, its own chunk,
 * loaded after hydration; under reduced motion, Save-Data, a slow connection or a video error the
 * stage falls back to the three stills (`data-still`, home-scenes.css).
 */
import { useEffect, useRef, useState } from "react";

import { startDemo } from "@/demo/session";
import { Link, useRouter } from "@/i18n/navigation";
import { useT, useThemeWord } from "@/theme/words";

import { Ghost } from "@/components/Ghost";
import { ScenePicture } from "./ScenePicture";

/** The Istanbul demo's findings, in the order of its recorded result (checked by a test). */
export const ISTANBUL_GHOSTS = [
  { rule: "pipc:5", position: 1, key: "pipc5" },
  { rule: "pipc:6", position: 2, key: "pipc6" },
  { rule: "pipc:9", position: 0, key: "pipc9" },
  { rule: "pipc:12", position: 3, key: "pipc12" },
] as const;

/**
 * Where the ghosts hover in the cabinet room, in front of the shelves they rose from (percent of
 * the image; same order as ISTANBUL_GHOSTS).
 */
const SHELVES = [
  { x: 70.5, y: 30 },
  { x: 78.5, y: 33 },
  { x: 69, y: 45 },
  { x: 77.5, y: 49 },
];

/** Where the ghosts rise in the diorama: shop windows and the door (percent of the image). */
const WINDOWS = [
  { x: 53.3, y: 49.4 },
  { x: 64.1, y: 65.7 },
  { x: 70.3, y: 63.7 },
  { x: 87, y: 60.4 },
];

export function NightPharmacyHero({ active }: { active: boolean }) {
  const t = useT();
  const w = useThemeWord();
  const router = useRouter();
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el || !active) return;
    let stop: (() => void) | undefined;
    let cancelled = false;
    void import("./nightMotion").then(({ startNightMotion }) => {
      if (!cancelled) stop = startNightMotion(el);
    });
    return () => {
      cancelled = true;
      stop?.();
    };
  }, [active]);

  const [hot, setHot] = useState<number | null>(null);
  const prepareNote = () => {
    startDemo("istanbul");
    router.push("/note");
  };
  const openFinding = (position: number) => {
    startDemo("istanbul");
    router.push(`/results/finding#${position}`);
  };
  const stepInside = () => {
    const el = root.current;
    const target = el?.querySelector<HTMLElement>("[data-scene3]");
    if (!target) return;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
    target.querySelector<HTMLElement>("h2")?.focus({ preventScroll: true });
  };

  return (
    <section
      ref={root}
      className="np"
      aria-labelledby="np-title"
      data-testid="night-hero"
    >
      <div className="np-copy">
        <div className="np-copy-inner">
          <p className="scene-eyebrow">{t("Home.tagline.twoFaces")}</p>
          <h1 id="np-title" className="scene-title">
            {t("Home.nightHeadline")}
          </h1>
          <p className="scene-lead">{t("Home.intro")}</p>
          <div className="flex flex-wrap gap-3">
            <Link href="/demo" className="scene-btn scene-btn-primary">
              {t("Home.demo")}
            </Link>
            <a href="#how-it-works" className="scene-btn">
              {t("Home.howTitle")}
            </a>
            <button type="button" className="scene-btn" onClick={stepInside}>
              {t("Home.stepInside")}
              <span aria-hidden>↓</span>
            </button>
          </div>
          <p className="scene-hint">{t("Home.demoHint")}</p>
        </div>
      </div>

      <div className="np-sticky" data-stage>
        <div className="scene np-hero">
          <div className="np-sky" aria-hidden />
          <div className="scene-box np-box-night">
            <ScenePicture name="night-diorama" alt={t("Home.alt.diorama")} />
            <div className="np-ghosts" aria-hidden>
              {WINDOWS.map((w, i) => (
                <span
                  key={i}
                  className="np-ghost"
                  data-ghost
                  style={{ left: `${w.x}%`, top: `${w.y}%` }}
                >
                  <Ghost size={64} animated />
                </span>
              ))}
            </div>
          </div>
          <div className="np-mist" aria-hidden />
          <canvas className="np-fireflies" aria-hidden data-fireflies />
        </div>
        <div className="scene np-video" aria-hidden>
          <div className="scene-box np-box-night">
            <video
              muted
              playsInline
              preload="none"
              disablePictureInPicture
              tabIndex={-1}
              data-video
            />
            <picture className="np-still-img">
              <source type="image/avif" srcSet="/home/door-mid-1280.avif" />
              <source type="image/webp" srcSet="/home/door-mid-1280.webp" />
              <img
                src="/home/door-mid-1280.jpg"
                alt=""
                width={1280}
                height={720}
                loading="lazy"
                decoding="async"
              />
            </picture>
          </div>
        </div>
        <div className="scene np-cabinet">
          <div className="scene-box np-box-cabinet">
            <ScenePicture name="night-cabinet" alt={t("Home.alt.cabinet")} />
            <span className="np-note-glow" aria-hidden />
            {/* Pointer shortcuts over the picture; the same actions are the buttons of the
                text column, so these stay out of the tab order and the accessibility tree. */}
            <div className="np-ghosts np-cabinet-ghosts" aria-hidden>
              {ISTANBUL_GHOSTS.map((g, i) => (
                <button
                  key={g.rule}
                  type="button"
                  tabIndex={-1}
                  className="np-ghost"
                  data-hot={hot === i ? "" : undefined}
                  style={{
                    left: `${SHELVES[i]!.x}%`,
                    top: `${SHELVES[i]!.y}%`,
                  }}
                  onPointerEnter={() => setHot(i)}
                  onPointerLeave={() => setHot(null)}
                  onClick={() => openFinding(g.position)}
                >
                  <Ghost size={56} animated />
                </button>
              ))}
            </div>
            <button
              type="button"
              tabIndex={-1}
              aria-hidden
              className="np-note-hotspot"
              onClick={prepareNote}
            />
          </div>
        </div>
      </div>
      <div className="np-runway" aria-hidden data-runway />

      <div
        className="np-scene3"
        data-scene3
        onFocus={(e) => {
          e.currentTarget.setAttribute("data-in", "");
          root.current?.setAttribute("data-in", "");
        }}
      >
        <div className="np-scene3-inner">
          <p className="scene-eyebrow">{t("Demo.label")}</p>
          <h2 tabIndex={-1} className="scene-title text-3xl outline-none">
            {w("Home.scene3Title")}
          </h2>
          <p className="scene-lead">{w("Home.scene3Intro")}</p>
          <ul className="flex flex-col gap-3">
            {ISTANBUL_GHOSTS.map((g, i) => {
              const label = t(`Home.ghosts.${g.key}`);
              return (
                <li key={g.rule}>
                  <button
                    type="button"
                    className="np-finding"
                    data-hot={hot === i ? "" : undefined}
                    aria-label={t("Home.ghostOpen", { finding: label })}
                    onClick={() => openFinding(g.position)}
                    onPointerEnter={() => setHot(i)}
                    onPointerLeave={() => setHot(null)}
                    onFocus={() => setHot(i)}
                    onBlur={() => setHot(null)}
                  >
                    <Ghost size={36} animated className="shrink-0" />
                    <span>{label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
          <div>
            <button
              type="button"
              className="scene-btn scene-btn-primary"
              onClick={prepareNote}
            >
              {t("Home.prepareDemoNote")}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

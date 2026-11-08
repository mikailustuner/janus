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
import { useEffect, useRef } from "react";

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

/** Where the ghosts rise in the cabinet room: the boxes on the shelves (percent of the image). */
const BOXES = [
  { x: 77.8, y: 32.9 },
  { x: 71.1, y: 42.8 },
  { x: 73.9, y: 46.8 },
  { x: 77.8, y: 47.8 },
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
            <div className="np-ghosts" aria-hidden>
              {BOXES.map((b, i) => (
                <span
                  key={i}
                  className="np-ghost"
                  style={{ left: `${b.x}%`, top: `${b.y}%` }}
                >
                  <Ghost size={64} animated />
                </span>
              ))}
            </div>
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
            {ISTANBUL_GHOSTS.map((g) => {
              const label = t(`Home.ghosts.${g.key}`);
              return (
                <li key={g.rule}>
                  <button
                    type="button"
                    className="np-finding"
                    aria-label={t("Home.ghostOpen", { finding: label })}
                    onClick={() => openFinding(g.position)}
                  >
                    <Ghost
                      size={44}
                      animated
                      className="shrink-0 drop-shadow-[0_0_10px_var(--ghost-edge)]"
                    />
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
              onClick={() => {
                startDemo("istanbul");
                router.push("/note");
              }}
            >
              {t("Home.prepareDemoNote")}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

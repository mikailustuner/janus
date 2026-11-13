"use client";
/**
 * Night Pharmacy home (steering design.md "Home scenes", experience Req 27.6–27.9, DP46, DP49).
 * Three scenes in one stage, switched by an explicit control, never by scroll:
 * - `hero`: the diorama with ghosts rising from the shop windows, the copy, and "Step inside"
 *   (a play button and a small scroll-down cue that does the same).
 * - `door`: the door transition video plays once, full-bleed, at normal speed in a fixed layer
 *   with a Skip control; at its end (or on Skip) it cross-fades into
 * - `room`: the medicine cabinet, where the ghosts hover as the Istanbul demo's findings (each a
 *   button into the demo), the glowing note is "Prepare the doctor note", and Replay plays the
 *   way in again. Focus moves to the scene 3 heading.
 * Under reduced motion, Save-Data, a slow connection or a video that cannot play, "Step inside"
 * cross-fades straight to the room and the video is never requested. The ambient motion
 * (fireflies, parallax, the ghosts' lean, pausing off-screen) and the idle preload of the video
 * live in `nightMotion.ts`, its own chunk.
 */
import { useEffect, useRef, useState } from "react";

import { startDemo } from "@/demo/session";
import { Link, useRouter } from "@/i18n/navigation";
import { useT, useThemeWord } from "@/theme/words";

import { Ghost } from "@/components/Ghost";
import {
  ChevronIcon,
  PlayIcon,
  ReplayIcon,
  SkipIcon,
} from "@/components/icons";
import { ScenePicture } from "./ScenePicture";
import { stillReason } from "./still";
import { loadDoorVideo } from "./video";

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

/** Fireflies: fixed positions (no randomness, so server and client render the same). */
const FIREFLIES = Array.from({ length: 16 }, (_, i) => ({
  x: (i * 37 + 11) % 100,
  y: 30 + ((i * 53) % 65),
  d: 7 + (i % 5) * 1.6,
  delay: -((i * 1.7) % 9),
}));

/** If the video has not started this long after "Step inside", go straight to the room. */
const START_TIMEOUT_MS = 6000;

type Scene = "hero" | "door" | "room";

export function NightPharmacyHero({ active }: { active: boolean }) {
  const t = useT();
  const w = useThemeWord();
  const router = useRouter();
  const root = useRef<HTMLElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const skip = useRef<HTMLButtonElement>(null);
  const enterButton = useRef<HTMLButtonElement>(null);
  const roomTitle = useRef<HTMLHeadingElement>(null);
  const [scene, setScene] = useState<Scene>("hero");
  const [hot, setHot] = useState<number | null>(null);
  // Where focus goes after the next scene change (null: leave it alone).
  const focusNext = useRef<"skip" | "room" | "enter" | null>(null);
  const startTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );

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

  useEffect(() => {
    const target = focusNext.current;
    focusNext.current = null;
    if (target === "skip") skip.current?.focus();
    else if (target === "enter") enterButton.current?.focus();
    else if (target === "room") {
      // The stage is at the top of the page; bring it back if the visitor scrolled (on phones
      // the button sits below the house). Instant: the video layer covers this jump.
      const top = root.current?.getBoundingClientRect().top ?? 0;
      if (top < 0) scrollBy({ top, behavior: "instant" });
      roomTitle.current?.focus({ preventScroll: true });
    }
  }, [scene]);

  useEffect(() => () => clearTimeout(startTimer.current), []);

  const toRoom = () => {
    clearTimeout(startTimer.current);
    video.current?.pause();
    focusNext.current = "room";
    setScene("room");
  };

  const stepInside = () => {
    const v = video.current;
    const el = root.current;
    if (!v || !el || stillReason() || el.hasAttribute("data-still")) {
      toRoom();
      return;
    }
    loadDoorVideo(v);
    clearTimeout(startTimer.current);
    startTimer.current = setTimeout(() => {
      if (v.paused || v.readyState < 3) toRoom();
    }, START_TIMEOUT_MS);
    v.currentTime = 0;
    v.play().catch(toRoom);
    focusNext.current = "skip";
    setScene("door");
  };

  const replay = () => {
    if (stillReason() || root.current?.hasAttribute("data-still")) {
      focusNext.current = "enter";
      setScene("hero");
    } else stepInside();
  };

  const prepareNote = () => {
    startDemo("istanbul");
    router.push("/note");
  };
  const openFinding = (position: number) => {
    startDemo("istanbul");
    router.push(`/results/finding#${position}`);
  };

  const room = scene === "room";

  return (
    <section
      ref={root}
      className="np"
      data-scene={scene}
      aria-labelledby="np-title"
      data-testid="night-hero"
    >
      <div className="np-stage" inert={scene === "door"}>
        <div className="scene np-hero" aria-hidden={room}>
          <div className="np-sky" aria-hidden />
          <div className="scene-box np-box-night">
            <ScenePicture
              name="night-diorama"
              alt={t("Home.alt.diorama")}
              first
            />
            <div className="np-ghosts" aria-hidden>
              {WINDOWS.map((p, i) => (
                <span
                  key={i}
                  className="np-ghost"
                  data-ghost
                  style={{ left: `${p.x}%`, top: `${p.y}%` }}
                >
                  <Ghost size={64} animated />
                </span>
              ))}
            </div>
          </div>
          <div className="np-mist" aria-hidden />
          <div className="np-fireflies" aria-hidden>
            {FIREFLIES.map((f, i) => (
              <span
                key={i}
                className="np-fly"
                style={{
                  left: `${f.x}%`,
                  top: `${f.y}%`,
                  animationDuration: `${f.d}s`,
                  animationDelay: `${f.delay}s`,
                }}
              />
            ))}
          </div>
        </div>

        <div className="scene np-cabinet" aria-hidden={!room}>
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

        <div className="np-copy">
          <div className="np-copy-inner">
            {/* In the room the heading stays for screen readers; the rest of the hero goes. */}
            {room ? null : (
              <p className="scene-eyebrow">{t("Home.tagline.twoFaces")}</p>
            )}
            <h1
              id="np-title"
              className={room ? "sr-only" : "scene-title np-title"}
            >
              {t("Home.nightHeadline")}
            </h1>
            {room ? null : (
              <>
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
                <div className="np-enter">
                  <button
                    ref={enterButton}
                    type="button"
                    className="scene-btn np-enter-btn"
                    onClick={stepInside}
                  >
                    <span className="np-enter-play" aria-hidden>
                      <PlayIcon size={18} />
                    </span>
                    {t("Home.stepInside")}
                  </button>
                  {/* A pointer shortcut for the same action; the button above is the control. */}
                  <button
                    type="button"
                    tabIndex={-1}
                    aria-hidden
                    className="np-cue"
                    onClick={stepInside}
                  >
                    <ChevronIcon size={26} />
                  </button>
                </div>
              </>
            )}
          </div>
          {room ? (
            <div className="np-scene3-inner">
              <p className="scene-eyebrow">{t("Demo.label")}</p>
              <h2
                ref={roomTitle}
                tabIndex={-1}
                className="scene-title text-3xl outline-none"
              >
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
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  className="scene-btn scene-btn-primary"
                  onClick={prepareNote}
                >
                  {t("Home.prepareDemoNote")}
                </button>
                <button type="button" className="scene-btn" onClick={replay}>
                  <ReplayIcon size={20} />
                  {t("Home.replay")}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* The door transition: decorative, full-bleed over the viewport while it plays. */}
      <div
        className="np-door"
        aria-hidden={scene !== "door"}
        onKeyDown={(e) => {
          if (e.key === "Escape") toRoom();
        }}
      >
        <video
          ref={video}
          muted
          playsInline
          preload="none"
          disablePictureInPicture
          tabIndex={-1}
          aria-hidden
          data-video
          onEnded={toRoom}
          onError={toRoom}
          onPlaying={() => clearTimeout(startTimer.current)}
        />
        <button
          ref={skip}
          type="button"
          className="scene-btn np-skip"
          tabIndex={scene === "door" ? 0 : -1}
          onClick={toRoom}
        >
          {t("Home.skip")}
          <SkipIcon size={18} />
        </button>
      </div>
    </section>
  );
}

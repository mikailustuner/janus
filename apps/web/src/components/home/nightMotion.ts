/**
 * Ambient motion of the Night Pharmacy home (own chunk, loaded after hydration; DP46, DP49).
 * Nothing here listens to scroll. The fireflies, the ghosts' float and the mist are CSS
 * animations of transform and opacity (compositor only); this script
 * - pauses every animation of the stage while it is off-screen (IntersectionObserver) or the
 *   tab is hidden (`data-paused`);
 * - eases the pointer parallax and the ghosts' lean toward the pointer in a requestAnimationFrame
 *   loop that runs only while the pointer moves (fine pointers only); the ghosts' centres are
 *   measured once per pointer entry and on resize, never inside the loop;
 * - preloads the door video once the page is idle (requestIdleCallback).
 * Under reduced motion, Save-Data or a slow connection none of this runs and the video is never
 * requested; Save-Data and 2G also set `data-still`, which stops the CSS animations.
 */
import { stillReason } from "./still";
import { loadDoorVideo } from "./video";

const clamp = (v: number, lo: number, hi: number) =>
  Math.min(hi, Math.max(lo, v));

export function startNightMotion(root: HTMLElement): () => void {
  const reason = stillReason();
  if (reason) {
    if (reason !== "reduce") root.setAttribute("data-still", reason);
    return () => {};
  }

  // Pause while off-screen or hidden.
  let onScreen = true;
  const setPaused = () =>
    root.toggleAttribute("data-paused", !onScreen || document.hidden);
  const io = new IntersectionObserver((entries) => {
    onScreen = entries.some((e) => e.isIntersecting);
    setPaused();
  });
  io.observe(root);
  document.addEventListener("visibilitychange", setPaused);

  // Video: only after the hero is idle; a poster covers the wait if "Step inside" comes first.
  const video = root.querySelector<HTMLVideoElement>("[data-video]");
  const idle =
    "requestIdleCallback" in window
      ? requestIdleCallback(() => video && loadDoorVideo(video), {
          timeout: 4000,
        })
      : setTimeout(() => video && loadDoorVideo(video), 2500);

  // Pointer parallax and lean.
  const fine = matchMedia("(pointer: fine)").matches;
  const ghosts = [...root.querySelectorAll<HTMLElement>("[data-ghost]")];
  let centres: { x: number; y: number }[] = [];
  const measure = () => {
    centres = ghosts.map((g) => {
      const b = g.getBoundingClientRect();
      return { x: b.left + b.width / 2, y: b.top + b.height / 2 };
    });
  };
  let mx = 0,
    my = 0,
    tx = 0,
    ty = 0,
    px = -1,
    raf = 0;
  const frame = () => {
    mx += (tx - mx) * 0.08;
    my += (ty - my) * 0.08;
    root.style.setProperty("--mx", mx.toFixed(4));
    root.style.setProperty("--my", my.toFixed(4));
    if (px >= 0)
      ghosts.forEach((g, i) => {
        const c = centres[i];
        if (!c) return;
        const dx = px - c.x;
        const lean = Math.abs(dx) < 420 ? clamp(dx / 420, -1, 1) * 12 : 0;
        g.style.setProperty("--lean", `${lean.toFixed(1)}deg`);
      });
    raf =
      Math.abs(tx - mx) + Math.abs(ty - my) > 0.002
        ? requestAnimationFrame(frame)
        : 0;
  };
  const onEnter = () => measure();
  const onPointer = (e: PointerEvent) => {
    tx = (e.clientX / innerWidth) * 2 - 1;
    ty = (e.clientY / innerHeight) * 2 - 1;
    px = e.clientX;
    if (!raf) raf = requestAnimationFrame(frame);
  };
  if (fine) {
    root.addEventListener("pointerenter", onEnter);
    root.addEventListener("pointermove", onPointer);
    addEventListener("resize", measure);
  }

  return () => {
    cancelAnimationFrame(raf);
    io.disconnect();
    document.removeEventListener("visibilitychange", setPaused);
    if ("cancelIdleCallback" in window) cancelIdleCallback(idle as number);
    else clearTimeout(idle);
    root.removeEventListener("pointerenter", onEnter);
    root.removeEventListener("pointermove", onPointer);
    removeEventListener("resize", measure);
  };
}

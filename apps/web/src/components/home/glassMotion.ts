/**
 * Motion of the Glass Janus home (own chunk; DP46, DP49, DP69): a gentle parallax of the floating
 * cards and capsules while a fine pointer moves over the hero (a requestAnimationFrame loop that
 * stops when they settle; the image itself never moves). The light sweep, the floating cards and
 * the capsules are CSS animations of transform and opacity; `data-paused` stops them while the hero is off-screen or the tab is hidden, and
 * `data-still` (Save-Data, slow connection) stops them for good. Nothing listens to scroll, and
 * nothing runs under reduced motion.
 */
import { stillReason } from "./still";

export function startGlassMotion(
  root: HTMLElement,
  pointer = true,
): () => void {
  const reason = stillReason();
  if (reason) {
    if (reason !== "reduce") root.setAttribute("data-still", reason);
    return () => {};
  }
  let onScreen = true;
  const setPaused = () =>
    root.toggleAttribute("data-paused", !onScreen || document.hidden);
  const io = new IntersectionObserver((entries) => {
    onScreen = entries.some((e) => e.isIntersecting);
    setPaused();
  });
  io.observe(root);
  document.addEventListener("visibilitychange", setPaused);

  let mx = 0,
    my = 0,
    tx = 0,
    ty = 0,
    raf = 0;
  const onPointer = (e: PointerEvent) => {
    tx = (e.clientX / innerWidth) * 2 - 1;
    ty = (e.clientY / innerHeight) * 2 - 1;
    if (!raf) raf = requestAnimationFrame(frame);
  };
  const frame = () => {
    mx += (tx - mx) * 0.08;
    my += (ty - my) * 0.08;
    root.style.setProperty("--mx", mx.toFixed(4));
    root.style.setProperty("--my", my.toFixed(4));
    raf =
      Math.abs(tx - mx) + Math.abs(ty - my) > 0.002
        ? requestAnimationFrame(frame)
        : 0;
  };
  const fine = pointer && matchMedia("(pointer: fine)").matches;
  if (fine) root.addEventListener("pointermove", onPointer);
  return () => {
    cancelAnimationFrame(raf);
    io.disconnect();
    document.removeEventListener("visibilitychange", setPaused);
    root.removeEventListener("pointermove", onPointer);
  };
}

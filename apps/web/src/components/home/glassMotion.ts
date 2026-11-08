/**
 * Motion of the Glass Janus home (own chunk; DP46): a gentle parallax and a subtle 3D tilt of
 * the head on pointer move. The light sweep and the capsule highlights are CSS (stopped by
 * `data-still` under Save-Data or a slow connection). Nothing runs under reduced motion or for
 * coarse pointers.
 */
import { stillReason } from "./still";

export function startGlassMotion(root: HTMLElement): () => void {
  const reason = stillReason();
  if (reason && reason !== "reduce") root.setAttribute("data-still", reason);
  if (reason || !matchMedia("(pointer: fine)").matches) return () => {};
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
  root.addEventListener("pointermove", onPointer);
  return () => {
    cancelAnimationFrame(raf);
    root.removeEventListener("pointermove", onPointer);
  };
}

/**
 * Motion of the Night Pharmacy home (own chunk, loaded after hydration; DP46). No library: one
 * requestAnimationFrame loop while the stage is on screen.
 * - Scroll progress p (0 → 1 over the runway) scrubs the door video (currentTime, one seek at a
 *   time; the files have a key frame every 6 frames) and crossfades diorama → video → cabinet.
 * - Pointer parallax on three layers (sky, house, mist) and the ghosts' curious lean.
 * - Fireflies and drifting dust on a canvas.
 * Still mode instead (no video request at all) under prefers-reduced-motion, Save-Data or a slow
 * connection; a video error switches to still mode too.
 */

import { stillReason } from "./still";

const clamp = (v: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const ramp = (p: number, a: number, b: number) => clamp((p - a) / (b - a));

export function startNightMotion(root: HTMLElement): () => void {
  const scene3 = root.querySelector<HTMLElement>("[data-scene3]");
  // Scene 3 entry (also in still mode: a fade, no movement under reduced motion).
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries)
        if (e.isIntersecting) {
          scene3?.setAttribute("data-in", "");
          root.setAttribute("data-in", "");
        }
    },
    { threshold: 0.25 },
  );
  if (scene3) io.observe(scene3);

  const reason = stillReason();
  if (reason) {
    if (reason !== "reduce") root.setAttribute("data-still", reason);
    return () => io.disconnect();
  }

  const video = root.querySelector<HTMLVideoElement>("[data-video]");
  const runway = root.querySelector<HTMLElement>("[data-runway]");
  const canvas = root.querySelector<HTMLCanvasElement>("[data-fireflies]");
  const ghosts = [...root.querySelectorAll<HTMLElement>("[data-ghost]")];
  const phone = matchMedia("(max-width: 767px)").matches;
  const finePointer = matchMedia("(pointer: fine)").matches;

  // Video: sources chosen by width; metadata first, the whole file once the page is idle.
  let duration = 0;
  if (video) {
    const w = phone ? 640 : 1280;
    for (const [type, ext] of [
      ["video/webm", "webm"],
      ["video/mp4", "mp4"],
    ] as const) {
      const s = document.createElement("source");
      s.type = type;
      s.src = `/home/door-${w}.${ext}`;
      video.appendChild(s);
    }
    video.preload = "metadata";
    video.load();
    video.addEventListener("loadedmetadata", () => {
      duration = video.duration || 0;
    });
    video.addEventListener(
      "error",
      () => root.setAttribute("data-still", "video"),
      true,
    );
    const full = () => {
      video.preload = "auto";
    };
    if ("requestIdleCallback" in window)
      requestIdleCallback(full, { timeout: 2500 });
    else setTimeout(full, 1500);
  }

  // Pointer parallax (fine pointers only), eased.
  let mx = 0,
    my = 0,
    tx = 0,
    ty = 0,
    px = -1,
    py = -1;
  const onPointer = (e: PointerEvent) => {
    tx = (e.clientX / innerWidth) * 2 - 1;
    ty = (e.clientY / innerHeight) * 2 - 1;
    px = e.clientX;
    py = e.clientY;
  };
  if (finePointer) root.addEventListener("pointermove", onPointer);

  // Fireflies and dust.
  const ctx = canvas?.getContext("2d") ?? null;
  const css = getComputedStyle(root);
  const fireflyColour = css.getPropertyValue("--scene-firefly").trim();
  const dustColour = css.getPropertyValue("--scene-muted").trim();
  type Mote = {
    x: number;
    y: number;
    r: number;
    s: number;
    ph: number;
    fly: boolean;
  };
  let motes: Mote[] = [];
  const sizeCanvas = () => {
    if (!canvas) return;
    const dpr = Math.min(2, devicePixelRatio || 1);
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = canvas.clientHeight * dpr;
    ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = phone ? 22 : 46;
    motes = Array.from({ length: n }, (_, i) => ({
      x: Math.random() * canvas.clientWidth,
      y: Math.random() * canvas.clientHeight,
      r: i % 3 === 0 ? 1.6 + Math.random() * 1.4 : 0.6 + Math.random() * 0.8,
      s: 0.15 + Math.random() * 0.35,
      ph: Math.random() * Math.PI * 2,
      fly: i % 3 === 0,
    }));
  };
  sizeCanvas();
  addEventListener("resize", sizeCanvas);

  let visible = true;
  const vio = new IntersectionObserver((e) => {
    visible = e.some((x) => x.isIntersecting);
    if (visible && !raf) raf = requestAnimationFrame(frame);
  });
  vio.observe(root);

  let raf = 0;
  let last = -1;
  let canvasLive = true;
  const frame = (now: number) => {
    if (!visible) {
      raf = 0;
      return;
    }
    // Scroll progress over the runway (the stage stays pinned while the runway scrolls by).
    const r = runway?.getBoundingClientRect();
    const span = Math.max(1, (runway?.offsetHeight ?? 1) - innerHeight);
    const p = r ? clamp((innerHeight - r.top) / span) : 0;
    root.style.setProperty("--g", String(1 - ramp(p, 0, 0.12)));
    root.style.setProperty("--h", String(1 - ramp(p, 0, 0.3)));

    root.style.setProperty("--v", String(ramp(p, 0.04, 0.12)));
    root.style.setProperty("--c", String(ramp(p, 0.86, 0.97)));
    if (video && duration && !video.seeking) {
      const t = ramp(p, 0.06, 0.92) * (duration - 0.05);
      if (Math.abs(t - last) > 1 / 48) {
        video.currentTime = t;
        last = t;
      }
    }
    // Parallax.
    mx += (tx - mx) * 0.06;
    my += (ty - my) * 0.06;
    root.style.setProperty("--mx", mx.toFixed(4));
    root.style.setProperty("--my", my.toFixed(4));
    if (px >= 0)
      for (const g of ghosts) {
        const b = g.getBoundingClientRect();
        const dx = px - (b.left + b.width / 2);
        const dy = py - (b.top + b.height / 2);
        const d = Math.hypot(dx, dy);
        const lean = d < 420 ? clamp(dx / 420, -1, 1) * 12 : 0;
        g.style.setProperty("--lean", `${lean.toFixed(1)}deg`);
      }
    // Fireflies: warm glows drifting up, faint dust drifting across.
    if (ctx && canvas && p >= 0.2 && canvasLive) {
      ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
      canvasLive = false;
    }
    if (ctx && canvas && p < 0.2) {
      canvasLive = true;
      const w = canvas.clientWidth,
        h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      for (const m of motes) {
        m.ph += 0.012;
        m.x += Math.sin(m.ph) * 0.3 + (m.fly ? 0 : m.s * 0.4);
        m.y -= m.fly ? m.s : m.s * 0.15;
        if (m.y < -10) m.y = h + 10;
        if (m.x > w + 10) m.x = -10;
        const a = m.fly ? 0.55 + 0.45 * Math.sin(now / 600 + m.ph * 3) : 0.25;
        ctx.globalAlpha = Math.max(0, a) * (1 - ramp(p, 0, 0.15));
        ctx.fillStyle = m.fly ? fireflyColour : dustColour;
        ctx.shadowColor = ctx.fillStyle;
        ctx.shadowBlur = m.fly ? 10 : 0;
        ctx.beginPath();
        ctx.arc(m.x, m.y, m.r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);

  return () => {
    cancelAnimationFrame(raf);
    io.disconnect();
    vio.disconnect();
    removeEventListener("resize", sizeCanvas);
    root.removeEventListener("pointermove", onPointer);
  };
}

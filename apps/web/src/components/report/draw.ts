/**
 * Draws the share card on a canvas and returns a PNG (janus-report DP10). Browser only; nothing is
 * sent anywhere. Colours are the active theme's tokens and the fonts the page's own, so the image
 * looks like the screen. The layout is measured first and scaled down when the person added long
 * lists, so every line (the disclaimer above all) stays on the image.
 */
import type { ShareCard } from "@/flow/share-card";

export const SHARE_WIDTH = 1080;
export const SHARE_HEIGHT = 1350;

interface Palette {
  bg: string;
  surface: string;
  fg: string;
  muted: string;
  accent: string;
  chip: string;
  chipFg: string;
  warn: string;
  risk: string;
  line: string;
  display: string;
  body: string;
}

function palette(): Palette {
  const s = getComputedStyle(document.documentElement);
  const v = (name: string, fallback: string) =>
    s.getPropertyValue(name).trim() || fallback;
  return {
    bg: v("--bg", "Canvas"),
    surface: v("--surface", "Canvas"),
    fg: v("--fg", "CanvasText"),
    muted: v("--muted", "GrayText"),
    accent: v("--accent", "CanvasText"),
    chip: v("--chip", "Canvas"),
    chipFg: v("--chip-fg", "CanvasText"),
    warn: v("--warn", "CanvasText"),
    risk: v("--risk", "CanvasText"),
    line: v("--line", "GrayText"),
    display: v("--font-display", "serif"),
    body: v("--font-body", "sans-serif"),
  };
}

type Ctx = CanvasRenderingContext2D;

function wrap(ctx: Ctx, text: string, width: number): string[] {
  const out: string[] = [];
  for (const para of text.split("\n")) {
    let line = "";
    for (const word of para.split(/\s+/).filter(Boolean)) {
      const next = line ? `${line} ${word}` : word;
      if (ctx.measureText(next).width <= width || !line) line = next;
      else {
        out.push(line);
        line = word;
      }
    }
    if (line) out.push(line);
  }
  return out;
}

function roundRect(
  ctx: Ctx,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
}

/** Lays out (and, with `paint`, draws) the card; returns the height used. */
function layout(
  ctx: Ctx,
  c: ShareCard,
  p: Palette,
  s: number,
  paint: boolean,
): number {
  const X = 104;
  const W = SHARE_WIDTH - 2 * X;
  let y = 112;
  const font = (weight: number, size: number, family: string) =>
    (ctx.font = `${weight} ${Math.round(size * s)}px ${family}`);
  const text = (
    str: string,
    size: number,
    color: string,
    { weight = 400, family = p.body, lh = 1.3, width = W, x = X } = {},
  ) => {
    font(weight, size, family);
    const lines = wrap(ctx, str, width);
    const step = size * s * lh;
    if (paint) {
      ctx.fillStyle = color;
      ctx.textBaseline = "alphabetic";
      lines.forEach((l, i) => ctx.fillText(l, x, y + size * s + i * step));
    }
    y += lines.length * step;
  };
  const gap = (px: number) => (y += px * s);

  if (c.demo) {
    font(700, 26, p.body);
    const w = ctx.measureText(c.demo).width + 44 * s;
    if (paint) {
      ctx.fillStyle = p.chip;
      roundRect(ctx, X, y, w, 50 * s, 25 * s);
      ctx.fill();
      ctx.fillStyle = p.chipFg;
      ctx.fillText(c.demo, X + 22 * s, y + 34 * s);
    }
    y += 50 * s;
    gap(28);
  }
  text(c.title, 64, p.fg, { weight: 600, family: p.display, lh: 1.15 });
  gap(6);
  text(c.month, 32, p.muted);
  gap(36);

  if (c.emergency) {
    const top = y;
    const inner = W - 56 * s;
    y += 26 * s;
    text(c.emergency, 30, p.fg, { weight: 700, width: inner, x: X + 28 * s });
    for (const line of c.safety) {
      gap(10);
      text(line, 30, p.risk, { weight: 700, width: inner, x: X + 28 * s });
    }
    y += 26 * s;
    if (paint) {
      ctx.strokeStyle = p.risk;
      ctx.lineWidth = 4 * s;
      roundRect(ctx, X, top, W, y - top, 28 * s);
      ctx.stroke();
    }
    gap(36);
  }

  // Big numbers on the left, the ring of the patterns checked on the right.
  const R = 118 * s;
  const ringX = X + W - R;
  const top = y;
  const statsW = W - 2 * R - 40 * s;
  for (const st of c.stats) {
    text(st.value, 132, p.fg, { weight: 800, lh: 1.0, width: statsW });
    gap(4);
    text(st.label, 32, p.muted, { width: statsW });
    gap(26);
  }
  const blockH = Math.max(y - top, 2 * R + 20 * s);
  if (paint) {
    const cy = top + R + 6 * s;
    ctx.lineCap = "round";
    ctx.lineWidth = 28 * s;
    ctx.strokeStyle = p.line;
    ctx.beginPath();
    ctx.arc(ringX, cy, R - 16 * s, 0, Math.PI * 2);
    ctx.stroke();
    const frac = c.rules.total ? c.rules.checked / c.rules.total : 0;
    ctx.strokeStyle = p.chipFg;
    ctx.beginPath();
    ctx.arc(
      ringX,
      cy,
      R - 16 * s,
      -Math.PI / 2,
      -Math.PI / 2 + frac * Math.PI * 2 - 0.12,
    );
    ctx.stroke();
    ctx.fillStyle = p.fg;
    ctx.textAlign = "center";
    font(800, 64, p.body);
    ctx.fillText(c.ringValue, ringX, cy + 10 * s);
    ctx.fillStyle = p.muted;
    font(400, 24, p.body);
    ctx.fillText(c.ringLabel, ringX, cy + 46 * s);
    // The ring's own label under it, so it never reads as a score (safety review A1).
    ctx.fillStyle = p.fg;
    font(700, 26, p.body);
    ctx.fillText(c.ringCaption, ringX, cy + R + 44 * s, 2 * R + 60 * s);
    ctx.textAlign = "start";
  }
  y = top + Math.max(blockH, 2 * R + 64 * s);
  gap(18);
  text(c.headline, 28, p.muted);
  gap(10);
  if (c.order) {
    text(c.order, 26, p.muted);
    gap(22);
  } else gap(12);
  if (c.noPattern) {
    text(c.noPattern, 34, p.fg, { weight: 700 });
    gap(22);
  }
  if (c.discuss) {
    text(c.discuss, 32, p.fg);
    gap(22);
  }
  if (c.abruptStop) {
    text(c.abruptStop.count, 30, p.muted);
    gap(4);
    text(c.abruptStop.line, 32, p.warn, { weight: 700 });
    if (c.abruptStop.names) {
      gap(4);
      text(c.abruptStop.names, 28, p.fg);
    }
    gap(22);
  }
  for (const list of [c.events, c.ingredients]) {
    if (!list) continue;
    if (paint) {
      ctx.fillStyle = p.line;
      ctx.fillRect(X, y, W, 2 * s);
    }
    gap(20);
    text(list.heading, 28, p.muted, { weight: 700 });
    gap(6);
    // Events one per line (each with its order wording); ingredients as one wrapped line.
    if (list === c.ingredients) text(list.names.join(" · "), 30, p.fg);
    else
      for (const name of list.names) {
        text(name, 30, p.fg);
        gap(4);
      }
    gap(18);
  }
  return y;
}

function footer(ctx: Ctx, c: ShareCard, p: Palette): number {
  const X = 104;
  const W = SHARE_WIDTH - 2 * X;
  ctx.font = `400 26px ${p.body}`;
  const lines = wrap(ctx, c.disclaimer, W);
  return 48 + lines.length * 36 + 18 + 34 + 56;
}

function paintFooter(ctx: Ctx, c: ShareCard, p: Palette, h: number) {
  const X = 104;
  const W = SHARE_WIDTH - 2 * X;
  const top = SHARE_HEIGHT - h;
  ctx.fillStyle = p.chip;
  ctx.fillRect(0, top, SHARE_WIDTH, h);
  ctx.fillStyle = p.fg;
  ctx.font = `400 26px ${p.body}`;
  const lines = wrap(ctx, c.disclaimer, W);
  lines.forEach((l, i) => ctx.fillText(l, X, top + 48 + 26 + i * 36));
  ctx.fillStyle = p.muted;
  ctx.font = `700 24px ${p.body}`;
  ctx.fillText(c.footer, X, top + 48 + lines.length * 36 + 18 + 26);
}

export async function drawShareCard(c: ShareCard): Promise<Blob> {
  const p = palette();
  // The page's fonts are normally loaded already; never wait more than 1.5 s for them.
  try {
    await Promise.race([
      Promise.all([
        document.fonts.load(`600 64px ${p.display}`),
        document.fonts.load(`800 64px ${p.body}`),
        document.fonts.load(`400 32px ${p.body}`),
      ]),
      new Promise((r) => setTimeout(r, 1500)),
    ]);
  } catch {
    /* system fonts then */
  }
  const canvas = document.createElement("canvas");
  canvas.width = SHARE_WIDTH;
  canvas.height = SHARE_HEIGHT;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("no 2d context");
  const fh = footer(ctx, c, p);
  const room = SHARE_HEIGHT - fh - 40;
  let s = 1;
  while (s > 0.5 && layout(ctx, c, p, s, false) > room) s -= 0.05;
  ctx.fillStyle = p.bg;
  ctx.fillRect(0, 0, SHARE_WIDTH, SHARE_HEIGHT);
  ctx.fillStyle = p.surface;
  ctx.fillRect(0, 0, SHARE_WIDTH, SHARE_HEIGHT);
  // A soft accent band on the leading edge: the image's one decoration.
  ctx.fillStyle = p.accent;
  ctx.fillRect(0, 0, 16, SHARE_HEIGHT - fh);
  layout(ctx, c, p, s, true);
  paintFooter(ctx, c, p, fh);
  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("toBlob failed"))),
      "image/png",
    ),
  );
}

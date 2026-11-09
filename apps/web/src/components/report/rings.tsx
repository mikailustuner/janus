/**
 * Rings and segmented bars of the Summary (janus-report Req 3, DP8). Decorative (`aria-hidden`):
 * the sentence or legend next to them carries the same numbers. A segment is told apart by its
 * stroke or fill pattern (solid, dashed, dotted, hatched) as well as its tone, never by colour
 * alone; tones are neutral tokens, never `--risk`.
 */
import type { ReactNode } from "react";

export type Mark = "solid" | "dashed" | "dotted" | "hatched";
export type Tone = "accent" | "chip" | "muted" | "fg";

export interface Segment {
  value: number;
  mark: Mark;
  tone: Tone;
}

const TONE: Record<Tone, string> = {
  accent: "stroke-accent",
  chip: "stroke-chip-fg",
  muted: "stroke-muted",
  fg: "stroke-fg",
};
const DASH: Record<Mark, string | undefined> = {
  solid: undefined,
  dashed: "9 7",
  dotted: "0.1 7.5",
  hatched: "3 4",
};

function arc(cx: number, cy: number, r: number, a0: number, a1: number) {
  const p = (a: number) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const [x0, y0] = p(a0) as [number, number];
  const [x1, y1] = p(a1) as [number, number];
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

/** Ring dashes in proportion to the stroke (round caps add half a stroke at each end). */
function ringDash(mark: Mark, w: number): string | undefined {
  if (mark === "dotted") return `0.1 ${(w * 1.55).toFixed(1)}`;
  if (mark === "dashed")
    return `${(w * 0.9).toFixed(1)} ${(w * 1.5).toFixed(1)}`;
  if (mark === "hatched")
    return `${(w * 0.3).toFixed(1)} ${(w * 1.3).toFixed(1)}`;
  return undefined;
}

/**
 * A segmented ring. `total` may exceed the sum of the segments (the rest stays as the track).
 * The centre holds the big number and its label.
 */
export function Ring({
  segments,
  total,
  size = 112,
  thickness = 12,
  children,
}: {
  segments: readonly Segment[];
  total: number;
  size?: number;
  thickness?: number;
  children?: ReactNode;
}) {
  const r = (size - thickness) / 2 - 1;
  const c = size / 2;
  const shown = segments.filter((s) => s.value > 0);
  // A small gap between segments; none when one segment fills the ring.
  const gap = shown.length > 1 || shown[0]?.value !== total ? 0.14 : 0;
  let a = -Math.PI / 2;
  const paths = total
    ? shown.map((s, i) => {
        const sweep = (s.value / total) * Math.PI * 2;
        const a0 = a + gap / 2;
        const a1 = a + sweep - gap / 2;
        a += sweep;
        if (sweep >= Math.PI * 2 - 1e-6)
          return (
            <circle
              key={i}
              cx={c}
              cy={c}
              r={r}
              fill="none"
              strokeWidth={thickness}
              strokeLinecap="round"
              strokeDasharray={ringDash(s.mark, thickness)}
              className={TONE[s.tone]}
            />
          );
        return (
          <path
            key={i}
            d={arc(c, c, r, a0, Math.max(a0 + 0.001, a1))}
            fill="none"
            strokeWidth={thickness}
            strokeLinecap="round"
            strokeDasharray={ringDash(s.mark, thickness)}
            className={TONE[s.tone]}
          />
        );
      })
    : [];
  return (
    <div
      className="ring-wrap relative grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
    >
      <svg
        aria-hidden
        focusable="false"
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="ring-svg absolute inset-0"
      >
        <circle
          cx={c}
          cy={c}
          r={r}
          fill="none"
          strokeWidth={thickness}
          className="stroke-line"
          opacity={0.7}
        />
        {paths}
      </svg>
      {children ? (
        <div className="relative flex flex-col items-center text-center leading-none">
          {children}
        </div>
      ) : null}
    </div>
  );
}

/** The legend mark: a short stroke with the segment's pattern and tone. */
export function MarkSwatch({ mark, tone }: { mark: Mark; tone: Tone }) {
  return (
    <svg
      aria-hidden
      focusable="false"
      width={28}
      height={10}
      viewBox="0 0 28 10"
      className="shrink-0"
    >
      <line
        x1={4}
        y1={5}
        x2={24}
        y2={5}
        strokeWidth={6}
        strokeLinecap="round"
        strokeDasharray={mark === "dotted" ? "0.1 6.5" : DASH[mark]}
        className={TONE[tone]}
      />
    </svg>
  );
}

/** A horizontal bar of segments with gaps; the fill pattern repeats the legend's mark. */
export function SegmentBar({ segments }: { segments: readonly Segment[] }) {
  const shown = segments.filter((s) => s.value > 0);
  return (
    <div aria-hidden className="flex h-5 w-full gap-1">
      {shown.map((s, i) => (
        <span
          key={i}
          className={`bar-seg bar-${s.mark} tone-${s.tone}`}
          style={{ flexGrow: s.value, flexBasis: 0 }}
        />
      ))}
    </div>
  );
}

/** The bar legend's mark: a small block with the bar segment's fill. */
export function BarSwatch({ mark, tone }: { mark: Mark; tone: Tone }) {
  return (
    <span
      aria-hidden
      className={`bar-seg bar-${mark} tone-${tone} inline-block h-3.5 w-6 shrink-0`}
    />
  );
}

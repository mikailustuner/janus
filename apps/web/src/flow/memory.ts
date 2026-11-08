/**
 * Collective Memory responses → panel view models (Req 16, P10). Pure. The assessment is kept
 * for the detail view only; list rows carry the report count and the range. A ratio is shown only
 * with its range; `no_reports` / `insufficient_data` show no ratio, only the coverage sentence and
 * `absence_is_not_reassurance`. Layers are never combined.
 */
import type { Assessment, PairOut, SharedOut, Stats } from "@/api/contracts";

export const OVER = 1000;

export interface Ratio {
  ror: number;
  low: number;
  high: number;
}

/** The ratio of a cell, or null when the API returned none or the counts are too few. */
export function ratioOf(stats: Stats | null): Ratio | null {
  if (!stats || !stats.estimates) return null;
  if (
    stats.assessment === "no_reports" ||
    stats.assessment === "insufficient_data"
  )
    return null;
  const { ror, ror_ci } = stats.estimates;
  return { ror, low: ror_ci.low, high: ror_ci.high };
}

export interface PairPanel {
  status: "ok" | "not_available";
  reports: number | null;
  ratio: Ratio | null;
  /** Detail view only (never in a list, a badge or a colour). */
  assessment: Assessment | null;
  /** Message keys under `Memory`, in the API's order; `screening_statistic` → `Memory.screening`. */
  sentences: string[];
  pts: string[];
  meddra: boolean;
  snapshotDate: string;
  window: string[];
}

const COVERAGE: Partial<Record<Assessment, string>> = {
  no_reports: "codes.no_reports",
  insufficient_data: "codes.insufficient_data",
};

export function noticeKey(code: string): string {
  return code === "screening_statistic" ? "screening" : `codes.${code}`;
}

export function pairPanel(p: PairOut): PairPanel {
  const stats = p.status === "ok" ? p.stats : null;
  const assessment = stats?.assessment ?? null;
  const sentences = p.notices.map(noticeKey);
  if (assessment && COVERAGE[assessment]) {
    sentences.push(COVERAGE[assessment]!);
    if (!sentences.includes("codes.absence_is_not_reassurance"))
      sentences.push("codes.absence_is_not_reassurance");
  } else if (assessment) sentences.push(`codes.${assessment}`);
  for (const c of stats?.codes ?? [])
    if (!sentences.includes(`codes.${c}`)) sentences.push(`codes.${c}`);
  return {
    status: p.status,
    reports: stats ? stats.cells.a : null,
    ratio: ratioOf(stats),
    assessment,
    sentences,
    pts: p.event.pts,
    meddra: p.event.pts.length > 0 && p.meddra_notice !== null,
    snapshotDate: p.snapshot.snapshot_date,
    window: p.snapshot.window,
  };
}

export interface SharedPanel {
  status: SharedOut["status"];
  cells: { region: string; value: number | null; hidden: boolean }[];
}

export function sharedPanel(s: SharedOut): SharedPanel {
  return {
    status: s.status,
    cells: s.cells.map((c) => ({
      region: c.region,
      value: c.status === "released" ? (c.value ?? null) : null,
      hidden: c.status === "hidden",
    })),
  };
}

/** Positions on a log axis for the confidence-interval bar (P11), in percent of the width. */
export function ciBar(
  r: Ratio,
  axis: { min: number; max: number } = { min: 0.1, max: OVER },
) {
  const clamp = (x: number) => Math.min(axis.max, Math.max(axis.min, x));
  const lmin = Math.log10(axis.min);
  const span = Math.log10(axis.max) - lmin;
  const pos = (x: number) => ((Math.log10(clamp(x)) - lmin) / span) * 100;
  return {
    low: pos(r.low),
    ror: pos(r.ror),
    high: pos(r.high),
    one: pos(1),
    lowClamped: r.low < axis.min,
    highClamped: r.high > axis.max,
    rorOver: r.ror > OVER,
  };
}

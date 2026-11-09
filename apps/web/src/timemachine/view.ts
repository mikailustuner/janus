/**
 * Pure view rules of the time-machine screens (experience Req 30, DP58–DP64; time-machine design
 * §10). No I/O and no medical number is derived here: the helpers choose what to show, map the
 * API's fixed English reasons to translation codes, place numbers on an axis and decide the one
 * patient-facing sentence (design §10.5).
 */
import index from "./index.json";
import type { Cascade, CascadeOut } from "./model";

export type ReasonCode =
  "no_pk" | "failed_credibility" | "no_potency" | "few_reports";

/**
 * The API sends its fixed reasons as English sentences (time-machine `build.py`); each known one
 * maps to a code with a translation (DP60). Anything else is shown verbatim in English.
 */
export function reasonCode(
  text: string | null | undefined,
): { code: ReasonCode; n?: number } | null {
  if (!text) return null;
  if (text === "no published human PK parameters for this constituent")
    return { code: "no_pk" };
  if (text === "model failed the credibility rule for this drug")
    return { code: "failed_credibility" };
  if (
    text.startsWith(
      "no measured potency on a curated, condition-relevant target",
    )
  )
    return { code: "no_potency" };
  const m = /^fewer than (\d+) reports with a usable interval$/.exec(text);
  if (m) return { code: "few_reports", n: Number(m[1]) };
  return null;
}

/**
 * Owner rule (DP59): the word PBPK never appears next to a compartmental model. The API's English
 * labels and notes say "(not PBPK)"; for a compartmental model they are replaced by the translated
 * method text, so an English source string is shown only when it does not contain the word.
 */
export function englishShownFor(
  method: Cascade["method"] | "compartmental",
  text: string,
): string | null {
  if (method === "compartmental" && /pbpk/i.test(text)) return null;
  return text;
}

export interface IndexEntry {
  id: string;
  pipc_position: number;
  index_keys: string[];
}

export const TM_INDEX = index as {
  built_at: string;
  substances: string[];
  cascades: IndexEntry[];
};

/** The time-machine cascades recorded for a PIPC row (cascade-map link, DP63). */
export function cascadesForRow(
  row: number,
  entries: readonly IndexEntry[] = TM_INDEX.cascades,
): IndexEntry[] {
  return entries.filter((e) => e.pipc_position === row);
}

export function hasSubstance(
  id: string,
  ids: readonly string[] = TM_INDEX.substances,
): boolean {
  return ids.includes(id);
}

/**
 * The one patient-facing sentence (design §10.5, Req 9; DP62). Shown only when exactly one
 * time-machine cascade has the finding's PIPC row and the finding's index ingredient among its
 * index drugs, its onset is not a small sample and agrees with the literature, and the middle half
 * is known. Returns the two day numbers, or null.
 */
export function patientTiming(
  row: number,
  indexKey: string,
  answers: readonly CascadeOut[],
  entries: readonly IndexEntry[] = TM_INDEX.cascades,
): { start: number; end: number } | null {
  const ids = new Set(
    entries
      .filter((e) => e.pipc_position === row && e.index_keys.includes(indexKey))
      .map((e) => e.id),
  );
  const hits = answers.filter(
    (a) => ids.has(a.cascade.cascade_id) && a.cascade.pipc_position === row,
  );
  if (hits.length !== 1) return null;
  const c = hits[0]!.cascade;
  const half = c.middle_half_days;
  if (!c.onset || c.onset.small_sample || c.agreement !== "agrees" || !half)
    return null;
  if (
    !Number.isFinite(half.start_days) ||
    !Number.isFinite(half.end_days) ||
    half.start_days < 0 ||
    half.end_days < half.start_days
  )
    return null;
  return {
    start: Math.round(half.start_days),
    end: Math.round(half.end_days),
  };
}

/** Whether the shape class may be named (design §10.3: never for a small sample). */
export function shapeShown(c: Cascade): boolean {
  return !!c.onset?.weibull && !c.onset.small_sample;
}

// --- axes ----------------------------------------------------------------------------------

export interface Axis {
  kind: "linear" | "log";
  min: number;
  max: number;
  ticks: number[];
}

/** A log axis over powers of ten that covers every positive value (concentrations). */
export function logAxis(values: readonly number[]): Axis {
  const pos = values.filter((v) => Number.isFinite(v) && v > 0);
  if (!pos.length)
    return { kind: "log", min: 0.1, max: 10, ticks: [0.1, 1, 10] };
  let lo = Math.floor(Math.log10(Math.min(...pos)));
  let hi = Math.ceil(Math.log10(Math.max(...pos)));
  if (hi === lo) hi += 1;
  if (hi - lo > 8) lo = hi - 8;
  const ticks: number[] = [];
  for (let e = lo; e <= hi; e++) ticks.push(Number(`1e${e}`));
  return { kind: "log", min: ticks[0]!, max: ticks.at(-1)!, ticks };
}

/** A linear axis from 0 with 4–6 round ticks (days). */
export function linearAxis(values: readonly number[]): Axis {
  const max = Math.max(1, ...values.filter((v) => Number.isFinite(v)));
  const raw = max / 5;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const step =
    [1, 2, 2.5, 5, 10].map((m) => m * pow).find((s) => s >= raw) ?? 10 * pow;
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + step / 2; v += step)
    ticks.push(Number(v.toPrecision(12)));
  return { kind: "linear", min: 0, max: top, ticks };
}

/** Position 0–1 of a value on the axis, clamped. */
export function place(axis: Axis, v: number): number {
  if (!Number.isFinite(v)) return 0;
  const f =
    axis.kind === "log"
      ? (Math.log10(Math.max(v, axis.min)) - Math.log10(axis.min)) /
        (Math.log10(axis.max) - Math.log10(axis.min))
      : (v - axis.min) / (axis.max - axis.min);
  return Math.min(1, Math.max(0, f));
}

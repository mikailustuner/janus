/**
 * The in-browser model explorer (simulation-service Req 1; owner decision 2026-11-09). Pure. The
 * explorer ships `explorer.json` (generated from the allow-list and the cited parameters by
 * `python -m janus.simulation.parity`) and runs the ported model on the device.
 *
 * Inputs are a compound, a predefined virtual population, a dose within the cited bounds and a
 * dosing schedule. There is no person-specific input (no body weight, age, sex, kidney or liver
 * function): `ExplorerInput` has exactly these fields, and a test keeps it so. Outputs are
 * distributions over the virtual population only.
 */
import data from "./explorer.json";
import { explore, horizon, type Exploration, type Params } from "./pk";

export interface Population {
  id: string;
  reference_keys: string[];
  params: Params;
}

export interface Compound {
  id: string;
  dose_mg: { low: number; default: number; high: number };
  intervals_h: number[];
  scenarios: { id: string; dose_mg: number; kind: string }[];
  populations: Population[];
  validation: {
    credibility: "credible" | "borderline" | "failed";
    cmax_fold: number;
    auc_fold: number;
    auc_independent: boolean;
    reference_key: string;
    cmax_direction: "model_lower" | "model_higher";
    auc_direction: "model_lower" | "model_higher";
  };
  validated_dose_mg: number[];
  reference_keys: string[];
}

export const EXPLORER = data as unknown as {
  version: string;
  compounds: Compound[];
  limits: {
    doses_max: number;
    horizon_after_last_dose_h: number;
    horizon_max_h: number;
  };
};

/** Samples drawn in the browser: enough for a stable 5-95 % band, fast on a phone. */
export const BROWSER_SAMPLES = 500;

export interface ExplorerInput {
  compound: string;
  population: string;
  dose_mg: number;
  /** null for one dose. */
  interval_h: number | null;
  doses: number;
}

export const INPUT_FIELDS = [
  "compound",
  "population",
  "dose_mg",
  "interval_h",
  "doses",
] as const;

export function compound(id: string): Compound | undefined {
  return EXPLORER.compounds.find((c) => c.id === id);
}

export function defaults(c: Compound = EXPLORER.compounds[0]!): ExplorerInput {
  return {
    compound: c.id,
    population: c.populations[0]!.id,
    dose_mg: c.dose_mg.default,
    interval_h: null,
    doses: 1,
  };
}

export type InputProblem =
  "compound" | "population" | "dose_mg" | "interval_h" | "doses";

/** Every field outside the allow-list's bounds (the form shows them, nothing runs). */
export function problems(i: ExplorerInput): InputProblem[] {
  const c = compound(i.compound);
  if (!c) return ["compound"];
  const out: InputProblem[] = [];
  if (!c.populations.some((p) => p.id === i.population)) out.push("population");
  if (!(
    Number.isFinite(i.dose_mg) &&
    i.dose_mg >= c.dose_mg.low &&
    i.dose_mg <= c.dose_mg.high
  ))
    out.push("dose_mg");
  if (!(
    Number.isInteger(i.doses) &&
    i.doses >= 1 &&
    i.doses <= EXPLORER.limits.doses_max
  ))
    out.push("doses");
  else if (
    i.doses === 1
      ? i.interval_h !== null
      : i.interval_h === null || !c.intervals_h.includes(i.interval_h)
  )
    out.push("interval_h");
  // Never cut a schedule short (pharmacologist review): it must fit the simulated time.
  else if (
    (i.doses - 1) * (i.interval_h ?? 0) +
      EXPLORER.limits.horizon_after_last_dose_h >
    EXPLORER.limits.horizon_max_h
  )
    out.push("doses");
  return out;
}

/** Outside the validated scenario: another dose than a validation dose, or repeated doses. */
export function extrapolated(i: ExplorerInput): boolean {
  const c = compound(i.compound);
  return !c || i.doses > 1 || !c.validated_dose_mg.includes(i.dose_mg);
}

export function hoursFor(
  i: Pick<ExplorerInput, "doses" | "interval_h">,
): number {
  return horizon(
    i.doses,
    i.interval_h,
    EXPLORER.limits.horizon_after_last_dose_h,
    EXPLORER.limits.horizon_max_h,
  );
}

/** The distribution over the chosen virtual population; null when an input is out of bounds. */
export function run(
  i: ExplorerInput,
  samples = BROWSER_SAMPLES,
): Exploration | null {
  if (problems(i).length) return null;
  const c = compound(i.compound)!;
  const p = c.populations.find((x) => x.id === i.population)!;
  return explore(
    p.params,
    i.dose_mg,
    hoursFor(i),
    samples,
    undefined,
    i.interval_h,
    i.doses,
  );
}

/** Rows of the table under the chart: every eighth time point and the last one. */
export function tableRows(e: {
  hours: readonly number[];
  p5_ng_ml: readonly number[];
  p50_ng_ml: readonly number[];
  p95_ng_ml: readonly number[];
}) {
  return e.hours
    .map((h, i) => ({
      h,
      p5: e.p5_ng_ml[i]!,
      p50: e.p50_ng_ml[i]!,
      p95: e.p95_ng_ml[i]!,
    }))
    .filter((_, i, all) => i % 8 === 0 || i === all.length - 1);
}

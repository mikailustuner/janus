/**
 * The time machine's minimal compartmental model, ported line by line from
 * `apps/api/janus/timemachine/pk.py` and `apps/api/janus/simulation/compartmental.py`
 * (simulation-service design §5, DP-S3). Runs entirely in the browser: one compartment,
 * first-order absorption with a lag, linear elimination, closed form (Bateman); Monte Carlo over
 * the cited spreads with Python's random generator, so the same input gives the same numbers as
 * the Python model (property S1). Never called PBPK.
 *
 * Units: dose mg, volume L, clearance L/h, rate constants 1/h, time h; outputs in ng/mL.
 */
import { PyRandom } from "./random";

const EPS = 1e-9;

export interface OneCompartment {
  f: number;
  ka: number;
  cl: number;
  v: number;
  tlag: number;
}

export function checkModel(m: OneCompartment): OneCompartment {
  if (!(m.f > 0 && m.f <= 1)) throw new Error("f must be in (0, 1]");
  if (!(m.ka > 0 && m.cl > 0 && m.v > 0 && m.tlag >= 0))
    throw new Error("ka, cl, v must be positive and tlag non-negative");
  return m;
}

const k = (m: OneCompartment) => m.cl / m.v;

function bateman(m: OneCompartment, dose: number, t: number): number {
  const tau = t - m.tlag;
  if (tau <= 0) return 0;
  const kk = k(m);
  const ka = m.ka;
  if (Math.abs(ka - kk) < EPS * Math.max(ka, kk))
    return (m.f * dose * ka * tau * Math.exp(-kk * tau)) / m.v;
  const c =
    ((m.f * dose * ka) / (m.v * (ka - kk))) *
    (Math.exp(-kk * tau) - Math.exp(-ka * tau));
  return Math.max(c, 0);
}

/**
 * Plasma concentration (mg/L) at time t after `n` doses every `tau` hours (first dose at 0), by
 * superposition (the model is linear), summed in the same order as Python.
 */
export function concentration(
  m: OneCompartment,
  dose: number,
  t: number,
  tau: number | null = null,
  n = 1,
): number {
  if (dose < 0 || n < 1)
    throw new Error("dose must be non-negative and n >= 1");
  if (n > 1 && (tau === null || tau <= 0))
    throw new Error("tau must be positive for repeated doses");
  const step = tau ?? 0;
  let sum = 0;
  for (let i = 0; i < n; i++)
    if (t - i * step > 0) sum += bateman(m, dose, t - i * step);
  return sum;
}

export function tmax(m: OneCompartment): number {
  const kk = k(m);
  const ka = m.ka;
  if (Math.abs(ka - kk) < EPS * Math.max(ka, kk)) return m.tlag + 1 / kk;
  return m.tlag + Math.log(ka / kk) / (ka - kk);
}

export const cmax = (m: OneCompartment, dose: number) =>
  bateman(m, dose, tmax(m));

/** AUC to infinity of one dose (mg h/L) = F D / CL. */
export const aucInf = (m: OneCompartment, dose: number) => (m.f * dose) / m.cl;

// --- uncertainty -------------------------------------------------------------------------------

export type Dist =
  | { kind: "lognormal"; median: number; gsd: number }
  | { kind: "uniform"; low: number; high: number };

function draw(d: Dist, rng: PyRandom): number {
  return d.kind === "lognormal"
    ? d.median * Math.exp(rng.gauss(0, Math.log(d.gsd)))
    : rng.uniform(d.low, d.high);
}

export interface ParamSpec {
  f: Dist;
  ka: Dist;
  cl: Dist;
  v: Dist;
  tlag: Dist;
}

/** Same draw order as Python: f, then ka, cl, v, tlag. */
function drawModel(s: ParamSpec, rng: PyRandom): OneCompartment {
  const f = Math.min(Math.max(draw(s.f, rng), 1e-6), 1);
  const ka = draw(s.ka, rng);
  const cl = draw(s.cl, rng);
  const v = draw(s.v, rng);
  const tlag = Math.max(draw(s.tlag, rng), 0);
  return checkModel({ f, ka, cl, v, tlag });
}

/** Linear-interpolation percentile, q in [0, 100]. */
export function percentile(values: readonly number[], q: number): number {
  if (!values.length) throw new Error("no values");
  const s = [...values].sort((a, b) => a - b);
  const pos = ((s.length - 1) * q) / 100;
  const lo = Math.floor(pos);
  const hi = Math.min(lo + 1, s.length - 1);
  return s[lo]! + (s[hi]! - s[lo]!) * (pos - lo);
}

export type Band = [p5: number, p50: number, p95: number];

const band = (v: readonly number[]): Band => [
  percentile(v, 5),
  percentile(v, 50),
  percentile(v, 95),
];

// --- the explorer (compartmental.py `explore`) -------------------------------------------------
// Owner decision 2026-11-09: no individualised simulation. Every output is a distribution over a
// predefined virtual population (5th, 50th, 95th percentile); there is no single-person curve.

export const SEED = 20261109;
export const POINTS = 385;

/** Medians of a virtual population and the spreads around them. */
export interface Params extends OneCompartment {
  ka_gsd: number;
  cl_gsd: number;
  v_gsd: number;
  /** Apparent parameters (F already in CL/F and V/F): no spread on F. */
  f_fixed?: boolean;
}

/** Hours simulated: until `afterLast` hours after the last dose, at most `cap`. */
export function horizon(
  doses: number,
  intervalH: number | null,
  afterLast: number,
  cap: number,
): number {
  return Math.min(cap, (doses - 1) * (intervalH ?? 0) + afterLast);
}

export function grid(hours: number): number[] {
  const step = hours / (POINTS - 1);
  return Array.from(
    { length: POINTS },
    (_, i) => Math.round(i * step * 1e9) / 1e9,
  );
}

export function spec(p: Params): ParamSpec {
  return {
    f: p.f_fixed
      ? { kind: "uniform", low: p.f, high: p.f }
      : { kind: "uniform", low: p.f * 0.8, high: Math.min(p.f * 1.2, 1) },
    ka: { kind: "lognormal", median: p.ka, gsd: p.ka_gsd },
    cl: { kind: "lognormal", median: p.cl, gsd: p.cl_gsd },
    v: { kind: "lognormal", median: p.v, gsd: p.v_gsd },
    tlag: { kind: "uniform", low: 0, high: p.tlag * 2 },
  };
}

export interface Exploration {
  hours: number[];
  p5_ng_ml: number[];
  p50_ng_ml: number[];
  p95_ng_ml: number[];
  peak_band_ng_ml: Band;
  auc_single_dose_band_ng_h_ml: Band;
}

export function explore(
  p: Params,
  doseMg: number,
  hours: number,
  samples: number,
  seed = SEED,
  intervalH: number | null = null,
  doses = 1,
): Exploration {
  const times = grid(hours);
  const s = spec(p);
  const rng = new PyRandom(seed);
  const curves: number[][] = [];
  const peaks: number[] = [];
  const aucs: number[] = [];
  for (let i = 0; i < samples; i++) {
    const mi = drawModel(s, rng);
    const c = times.map((t) => concentration(mi, doseMg, t, intervalH, doses));
    curves.push(c);
    peaks.push(Math.max(...c));
    aucs.push(aucInf(mi, doseMg));
  }
  const K = 1000;
  const per = times.map((_, j) => band(curves.map((c) => c[j]!)));
  const peak = band(peaks);
  const auc = band(aucs);
  return {
    hours: times,
    p5_ng_ml: per.map((b) => b[0] * K),
    p50_ng_ml: per.map((b) => b[1] * K),
    p95_ng_ml: per.map((b) => b[2] * K),
    peak_band_ng_ml: [peak[0] * K, peak[1] * K, peak[2] * K],
    auc_single_dose_band_ng_h_ml: [auc[0] * K, auc[1] * K, auc[2] * K],
  };
}

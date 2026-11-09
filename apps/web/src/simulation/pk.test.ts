// simulation-service property S1: the browser port matches the Python model on the shared
// fixtures (`python -m janus.simulation.parity`): the same random draws for the same seed, and
// the same explorer output for the allow-listed compounds at cited and random parameters.
// S2: the closed form conserves the usual invariants (non-negative, linear in dose, AUC = F D / CL
// against numerical integration).
import fc from "fast-check";
import { describe, expect, it } from "vitest";

import fixture from "./parity.fixture.json";
import { aucInf, cmax, concentration, explore, tmax, type Params } from "./pk";
import { PyRandom } from "./random";

const close = (a: number, b: number, rel = 1e-9) =>
  Math.abs(a - b) <= rel * Math.max(1, Math.abs(a), Math.abs(b));

function expectClose(actual: unknown, expected: unknown, path = "$"): void {
  if (typeof expected === "number") {
    expect(typeof actual, path).toBe("number");
    expect(
      close(actual as number, expected),
      `${path}: ${actual} vs ${expected}`,
    ).toBe(true);
  } else if (Array.isArray(expected)) {
    expect(Array.isArray(actual), path).toBe(true);
    expect((actual as unknown[]).length, path).toBe(expected.length);
    expected.forEach((e, i) =>
      expectClose((actual as unknown[])[i], e, `${path}[${i}]`),
    );
  }
}

describe("S1: parity with the Python model", () => {
  it("PyRandom reproduces CPython's draws", () => {
    for (const d of fixture.draws) {
      const r = new PyRandom(d.seed);
      // random() must be bit-identical (integer arithmetic only).
      expect(Array.from({ length: d.random.length }, () => r.random())).toEqual(
        d.random,
      );
      expectClose(
        Array.from({ length: d.gauss.length }, () => r.gauss(0, 1)),
        d.gauss,
      );
      expectClose(
        Array.from({ length: d.uniform.length }, () => r.uniform(2, 5)),
        d.uniform,
      );
    }
  });

  it("explore() matches compartmental.explore on every shared case", () => {
    expect(fixture.cases.length).toBeGreaterThanOrEqual(9);
    for (const c of fixture.cases) {
      const out = explore(
        c.params as Params,
        c.dose_mg,
        c.hours,
        c.samples,
        c.seed,
        c.interval_h,
        c.doses,
      );
      for (const key of Object.keys(out) as (keyof typeof out)[])
        expectClose(
          out[key],
          (c.out as Record<string, unknown>)[key],
          `${c.compound}.${key}`,
        );
    }
  });
});

const modelArb = fc.record({
  f: fc.double({ min: 0.05, max: 1, noNaN: true }),
  ka: fc.double({ min: 0.05, max: 5, noNaN: true }),
  cl: fc.double({ min: 0.5, max: 60, noNaN: true }),
  v: fc.double({ min: 5, max: 2500, noNaN: true }),
  tlag: fc.double({ min: 0, max: 1, noNaN: true }),
});

describe("S2: closed-form invariants", () => {
  it("never negative, zero before the lag, linear in dose", () => {
    fc.assert(
      fc.property(
        modelArb,
        fc.double({ min: 0, max: 200, noNaN: true }),
        fc.double({ min: 0.1, max: 1000, noNaN: true }),
        (m, t, dose) => {
          const c = concentration(m, dose, t);
          expect(c).toBeGreaterThanOrEqual(0);
          if (t <= m.tlag) expect(c).toBe(0);
          expect(close(concentration(m, 2 * dose, t), 2 * c, 1e-9)).toBe(true);
        },
      ),
    );
  });

  it("Cmax is the maximum and AUC = F·D/CL agrees with integration", () => {
    fc.assert(
      fc.property(modelArb, (m) => {
        const dose = 10;
        const tm = tmax(m);
        const cm = cmax(m, dose);
        for (const dt of [-0.5, -0.1, 0.1, 0.5])
          expect(concentration(m, dose, tm + dt)).toBeLessThanOrEqual(
            cm * (1 + 1e-12),
          );
        const end = m.tlag + (40 * Math.log(2)) / (m.cl / m.v) + 40 / m.ka;
        const steps = 20000;
        const h = end / steps;
        let auc = 0;
        for (let i = 0; i < steps; i++)
          auc +=
            (h *
              (concentration(m, dose, i * h) +
                concentration(m, dose, (i + 1) * h))) /
            2;
        expect(Math.abs(auc - aucInf(m, dose)) / aucInf(m, dose)).toBeLessThan(
          0.01,
        );
      }),
      { numRuns: 40 },
    );
  });

  it("repeated doses superpose single doses", () => {
    fc.assert(
      fc.property(
        modelArb,
        fc.integer({ min: 6, max: 48 }),
        fc.integer({ min: 1, max: 14 }),
        fc.double({ min: 0, max: 400, noNaN: true }),
        (m, tau, n, t) => {
          let sum = 0;
          for (let i = 0; i < n; i++) sum += concentration(m, 10, t - i * tau);
          expect(close(concentration(m, 10, t, tau, n), sum, 1e-12)).toBe(true);
        },
      ),
    );
  });

  it("the band is ordered and seeded; no single-person curve exists", () => {
    const p = fixture.cases[0]!.params as Params;
    const a = explore(p, 10, 48, 80);
    const b = explore(p, 10, 48, 80);
    expect(Object.keys(a).sort()).toEqual(
      [
        "auc_single_dose_band_ng_h_ml",
        "hours",
        "p50_ng_ml",
        "p5_ng_ml",
        "p95_ng_ml",
        "peak_band_ng_ml",
      ].sort(),
    );
    expect(a).toEqual(b);
    a.hours.forEach((_, i) => {
      expect(a.p5_ng_ml[i]!).toBeLessThanOrEqual(a.p50_ng_ml[i]!);
      expect(a.p50_ng_ml[i]!).toBeLessThanOrEqual(a.p95_ng_ml[i]!);
    });
  });
});

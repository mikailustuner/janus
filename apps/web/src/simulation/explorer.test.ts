// simulation-service properties on the web side (owner decision 2026-11-09):
// S2  the explorer and the server form have no person-specific input; results are distributions
//     only; every recorded server answer carries the virtual-population sentence
// S8  the model screens never import patient data (medicine list, findings, scans, notes) and link
//     to no patient screen
// plus: bounds of the explorer equal the allow-list; out-of-bounds inputs never run.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import * as D from "@/api/decode";

import {
  defaultRequest,
  demoSimulation,
  job,
  serverCompounds,
  type SimulationFixture,
} from "./client";
import {
  defaults,
  EXPLORER,
  INPUT_FIELDS,
  problems,
  run,
  type ExplorerInput,
} from "./explorer";
import parity from "./parity.fixture.json";
import recorded from "./simulate.recorded.json";

const SENTENCE =
  "Virtual population, for research. Not about any person and not a dose recommendation.";
const PERSON =
  /weight|bw|kg|height|bmi|age|sex|gender|creat|egfr|gfr|kidney|renal|liver|hepat|genotype|cyp|pregnan|name|patient|person|birth/i;
const fx = recorded as unknown as SimulationFixture;

describe("S2: no individualised simulation", () => {
  it("the explorer input has exactly the allowed, non-personal fields", () => {
    expect(Object.keys(defaults()).sort()).toEqual([...INPUT_FIELDS].sort());
    for (const f of INPUT_FIELDS) expect(f).not.toMatch(PERSON);
  });

  it("the server requests the form can build have no personal field", () => {
    const c = D.decode(serverCompounds, fx.compounds);
    if (!c.ok) throw new Error("recorded compounds do not decode");
    for (const kind of ["compartmental", "httk_population"] as const)
      for (const k of Object.keys(defaultRequest(c.value, kind)))
        expect(k).not.toMatch(PERSON);
  });

  it("every recorded server answer carries the sentence and is a distribution", async () => {
    const c = D.decode(serverCompounds, fx.compounds);
    expect(c.ok && c.value.disclaimer.startsWith(SENTENCE)).toBe(true);
    const client = demoSimulation(fx);
    for (const j of fx.jobs) {
      const r = await client.submit(j.request);
      expect(r.ok).toBe(true);
      if (!r.ok) continue;
      expect(r.data.disclaimer.startsWith(SENTENCE)).toBe(true);
      const res = r.data.result!;
      if (res.model === "compartmental") {
        expect(res.p5_ng_ml.length).toBe(res.hours.length);
        res.hours.forEach((_, i) => {
          expect(res.p5_ng_ml[i]!).toBeLessThanOrEqual(res.p50_ng_ml[i]!);
          expect(res.p50_ng_ml[i]!).toBeLessThanOrEqual(res.p95_ng_ml[i]!);
        });
      } else {
        // Both predefined age ranges, the comparison is the result.
        expect(res.groups.map((g) => g.population)).toEqual([
          "adult",
          "adult_65plus",
        ]);
        for (const g of res.groups) {
          const [a, b, d] = g.css_band_mg_l;
          expect(a! <= b! && b! <= d!).toBe(true);
        }
        expect(res.older_to_younger_median_ratio).toBeCloseTo(
          res.groups[1]!.css_band_mg_l[1]! / res.groups[0]!.css_band_mg_l[1]!,
          9,
        );
      }
      expect(Object.keys(res).some((k) => /^(point|cmax|tmax)/.test(k))).toBe(
        false,
      );
    }
  });

  it("the job decoder refuses an answer without the disclaimer", () => {
    const j = fx.jobs[0]!.job as Record<string, unknown>;
    const without = Object.fromEntries(
      Object.entries(j).filter(([k]) => k !== "disclaimer"),
    );
    expect(D.decode(job, without).ok).toBe(false);
  });

  it("a request the demo did not record is refused, never invented", async () => {
    const r = await demoSimulation(fx).submit({
      kind: "httk_population",
      compound: "risperidone",
      samples: 100,
    });
    expect(!r.ok && r.error.messageKey).toBe("Simulation.errors.demoOnly");
  });
});

const inputArb: fc.Arbitrary<ExplorerInput> = fc.record({
  compound: fc.constantFrom(...EXPLORER.compounds.map((c) => c.id), "caffeine"),
  population: fc.constantFrom("adult", "adult_65plus", "child"),
  dose_mg: fc.oneof(
    fc.double({ min: -10, max: 1000, noNaN: true }),
    fc.constant(Number.NaN),
  ),
  interval_h: fc.oneof(fc.constant(null), fc.integer({ min: 0, max: 100 })),
  doses: fc.integer({ min: 0, max: 20 }),
});

describe("explorer bounds", () => {
  it("runs exactly when every input is inside the allow-list's bounds", () => {
    fc.assert(
      fc.property(inputArb, (i) => {
        const p = problems(i);
        const out = run(i, 20);
        expect(out === null).toBe(p.length > 0);
        if (out)
          expect(out.p50_ng_ml.every((x) => Number.isFinite(x) && x >= 0)).toBe(
            true,
          );
      }),
      { numRuns: 60 },
    );
  });

  it("the shipped populations are the ones the Python model was checked with", () => {
    for (const c of EXPLORER.compounds)
      for (const p of c.populations) {
        const k = parity.cases.find(
          (x) => x.compound === c.id && x.population === p.id,
        );
        expect(k?.params).toEqual(p.params);
      }
  });
});

describe("S8: the model screens never touch patient data", () => {
  const dirs = [
    join(import.meta.dirname, "../components/simulation"),
    import.meta.dirname,
  ];
  const files = dirs.flatMap((d) =>
    readdirSync(d)
      .filter((f) => /\.tsx?$/.test(f) && !f.endsWith(".test.ts"))
      .map((f) => join(d, f)),
  );
  it.each(files)("%s", (file) => {
    const src = readFileSync(file, "utf8");
    expect(src).not.toMatch(
      /from "@\/(store|flow\/(?!useCall")|scan|note|passport|results|report|doctor|consent|demo\/fixtures)/,
    );
    expect(src).not.toMatch(
      /href=\{?["'`]\/(medicines|results|scan|note|timeline|passport|confirm|start|donate)/,
    );
  });
});

describe("messages", () => {
  it("the sentence exists in every locale", () => {
    for (const l of ["en", "tr", "de", "fr", "es"]) {
      const m = JSON.parse(
        readFileSync(
          join(import.meta.dirname, `../../messages/${l}.json`),
          "utf8",
        ),
      );
      expect(m.Simulation.virtualPopulation.length).toBeGreaterThan(20);
    }
    const en = JSON.parse(
      readFileSync(join(import.meta.dirname, "../../messages/en.json"), "utf8"),
    );
    expect(en.Simulation.virtualPopulation).toBe(SENTENCE);
  });
});

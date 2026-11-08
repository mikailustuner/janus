// Feature: experience, Properties P10 (memory display rules) and P11 (CI bar and numbers).
import { describe, expect, it } from "vitest";

import { formatRatio } from "@/components/format";
import { ratioText } from "@/components/memory/CiBar";
import { check, fc } from "@/test/fc";
import { PAIRS } from "@/test/results";
import type { Assessment, PairOut, SharedOut } from "@/api/contracts";

import { ciBar, OVER, pairPanel, ratioOf, sharedPanel } from "./memory";

const assessments: Assessment[] = [
  "no_reports",
  "insufficient_data",
  "not_disproportionate",
  "weak",
  "disproportionate",
];

describe("P10 memory display", () => {
  it("shows a ratio only with its range and never for no_reports / insufficient_data", () => {
    check(
      fc.property(
        fc.constantFrom(...PAIRS),
        fc.constantFrom(...assessments),
        fc.boolean(),
        (base, a, noEstimates) => {
          const p: PairOut = {
            ...base,
            stats: base.stats && {
              ...base.stats,
              assessment: a,
              estimates: noEstimates ? null : base.stats.estimates,
            },
          };
          const v = pairPanel(p);
          if (a === "no_reports" || a === "insufficient_data") {
            expect(v.ratio).toBeNull();
            expect(v.sentences).toContain(`codes.${a}`);
            expect(v.sentences).toContain("codes.absence_is_not_reassurance");
          } else if (!noEstimates && base.stats?.estimates) {
            expect(v.ratio).toEqual({
              ror: base.stats!.estimates!.ror,
              low: base.stats!.estimates!.ror_ci.low,
              high: base.stats!.estimates!.ror_ci.high,
            });
          }
          // the limits, the window and the screening sentence are always there
          for (const k of [
            "codes.spontaneous_reporting",
            "codes.not_incidence",
            "codes.deduplicated_by_case_version_only",
            "screening",
          ])
            expect(v.sentences).toContain(k);
          expect(v.reports).toBe(p.stats?.cells.a ?? null);
        },
      ),
    );
  });
  it("renders hidden cells as hidden and never adds numbers across layers", () => {
    check(
      fc.property(
        fc.array(
          fc.record({
            region: fc.constantFrom(
              "TR" as const,
              "EU" as const,
              "US" as const,
            ),
            status: fc.constantFrom("released" as const, "hidden" as const),
            value: fc.option(fc.nat(), { nil: null }),
          }),
          { maxLength: 3 },
        ),
        (cells) => {
          const s: SharedOut = {
            layer: "outcomes",
            status: "ok",
            cells,
            total_of_released: null,
            disclosure: {
              k: 20,
              epsilon: "1",
              wording: "hidden_under_20_noise_added",
            },
            disclaimer: "",
            notices: [],
          };
          const v = sharedPanel(s);
          v.cells.forEach((c, i) => {
            expect(c.hidden).toBe(cells[i]!.status === "hidden");
            if (c.hidden) expect(c.value).toBeNull();
          });
          expect(Object.keys(v)).toEqual(["status", "cells"]); // no total, no cross-layer sum
        },
      ),
    );
  });
  it("keeps the assessment out of everything but the detail field", () => {
    for (const p of PAIRS) {
      const v = pairPanel(p);
      expect(v.assessment).toBe(p.stats?.assessment ?? null);
      expect(ratioOf(p.stats)).toEqual(v.ratio);
    }
  });
});

describe("P11 CI bar and numbers", () => {
  const value = fc.oneof(
    fc.constantFrom(0.005, 1, 999.9, 1000.1, 1e6),
    fc.double({ min: 0.001, max: 1e6, noNaN: true }),
  );
  it("orders the positions on the log axis and clamps beyond the edges", () => {
    check(
      fc.property(value, value, value, (a, b, c) => {
        const [low, ror, high] = [a, b, c].sort((x, y) => x - y) as [
          number,
          number,
          number,
        ];
        const bar = ciBar({ low, ror, high });
        expect(bar.low).toBeLessThanOrEqual(bar.ror);
        expect(bar.ror).toBeLessThanOrEqual(bar.high);
        for (const x of [bar.low, bar.ror, bar.high, bar.one])
          expect(x >= 0 && x <= 100).toBe(true);
        expect(bar.highClamped).toBe(high > OVER);
        expect(bar.rorOver).toBe(ror > OVER);
      }),
    );
  });
  it("formats with the locale's decimal separator and says 'over 1,000' above 1,000", () => {
    expect(formatRatio(5.135, "en")).toBe("5.14");
    expect(formatRatio(5.135, "tr")).toBe("5,14");
    expect(formatRatio(5.135, "de")).toBe("5,14");
    expect(ratioText(1000.1, "en", "over 1,000")).toBe("over 1,000");
    expect(ratioText(999.9, "fr", "plus de 1 000")).toMatch(/^1\s000$/u);
    check(
      fc.property(
        fc.double({ min: 0.001, max: 1000, noNaN: true }),
        fc.constantFrom("en", "tr", "de", "fr", "es"),
        (x, l) => {
          expect(ratioText(x, l, "OVER")).toBe(formatRatio(x, l));
        },
      ),
    );
  });
});

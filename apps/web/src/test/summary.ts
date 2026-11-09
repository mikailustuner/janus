/** Arbitraries for the Summary (janus-report design §6): results with any timing, on demo items. */
import type { CascadeResult } from "@/api/contracts";
import { demoItems, type Fixture } from "@/demo/client";

import { fc } from "./fc";
import { cascadeResultArb, FIXTURES } from "./results";

export const ITEMS = FIXTURES.flatMap((f) =>
  demoItems(f as unknown as Fixture),
);
const TIMINGS = [
  "within_window",
  "after_window",
  "same_month",
  "date_unknown",
] as const;

/** A result with any timing per finding, on a list of n items drawn from the demo items. */
export const summaryInputArb = fc
  .record({
    base: cascadeResultArb,
    timings: fc.array(fc.constantFrom(...TIMINGS), { maxLength: 8 }),
    picks: fc.array(fc.nat({ max: ITEMS.length - 1 }), { maxLength: 15 }),
  })
  .map(({ base: { result, n }, timings, picks }) => {
    const r: CascadeResult = {
      ...result,
      findings: result.findings.map((f, k) => ({
        ...f,
        timing: timings[k] ?? f.timing,
      })),
    };
    const items = Array.from(
      { length: n },
      (_, i) => ITEMS[picks[i] ?? i % ITEMS.length]!,
    );
    return { r, items };
  });

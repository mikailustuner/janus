// Feature: report-assistant, Property P8 (design §5): prefill fragments carry codes only.
import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";

import { buildPrefill, parsePrefill, type Prefill } from "./fragment";

const key = fc.oneof(
  fc.integer({ min: 1, max: 99_999_999 }).map((n) => `Q${n}`),
  fc.integer({ min: 1, max: 99_999 }).map((n) => `J${n}`),
);
const prefillArb: fc.Arbitrary<Prefill> = fc.oneof(
  fc.constant({ src: "list" as const }),
  fc.record({
    src: fc.constant("finding" as const),
    ingredient: key,
    event: fc.option(fc.stringMatching(/^[a-z][a-z0-9_]{0,20}$/), {
      nil: null,
    }),
    items: fc.uniqueArray(fc.integer({ min: 0, max: 499 }), { maxLength: 5 }),
  }),
  fc
    .record({
      src: fc.constant("doctor" as const),
      rule: fc.integer({ min: 1, max: 65 }).map((n) => `pipc:${n}`),
      ingredient: key,
      others: fc.uniqueArray(key, { maxLength: 5 }),
      demo: fc.boolean(),
    })
    .map((p) => ({ ...p, others: p.others.filter((k) => k !== p.ingredient) })),
);

describe("prefill fragments", () => {
  it("P8: build → parse round-trips", () => {
    check(
      fc.property(prefillArb, (p) => {
        expect(parsePrefill(`#${buildPrefill(p)}`)).toEqual(p);
      }),
    );
  });

  it("P8: any string parses without throwing to well-formed codes or null", () => {
    check(
      fc.property(fc.string({ maxLength: 200 }), (s) => {
        const p = parsePrefill(s);
        if (!p || p.src === "list") return;
        expect(p.ingredient).toMatch(/^(Q|J)[1-9][0-9]*$/);
        if (p.src === "finding") {
          if (p.event) expect(p.event).toMatch(/^[a-z][a-z0-9_]*$/);
          for (const i of p.items) expect(i).toBeLessThan(500);
        } else {
          expect(p.rule).toMatch(/^pipc:[1-9][0-9]*$/);
          for (const k of p.others) expect(k).toMatch(/^(Q|J)[1-9][0-9]*$/);
        }
      }),
    );
  });

  it("P8: free text, names and dates are dropped", () => {
    expect(
      parsePrefill("#src=finding&ing=Q668093&event=Muscle%20pain&items=0,x,2"),
    ).toEqual({
      src: "finding",
      ingredient: "Q668093",
      event: null,
      items: [0, 2],
    });
    expect(parsePrefill("#src=doctor&rule=pipc:9&ing=ATOR")).toBeNull();
    expect(parsePrefill("#src=doctor&rule=1&ing=Q1")).toBeNull();
    expect(parsePrefill("#name=Ayse")).toBeNull();
    expect(parsePrefill("")).toBeNull();
    const built = buildPrefill({
      src: "doctor",
      rule: "pipc:9",
      ingredient: "Q668093",
      others: ["Q57055"],
      demo: true,
    });
    expect(built).toBe(
      "src=doctor&rule=pipc%3A9&ing=Q668093&with=Q57055&demo=1",
    );
  });
});

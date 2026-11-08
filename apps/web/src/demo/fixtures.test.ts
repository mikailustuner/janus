// Tasks 7.1–7.3: the recorded demo cases, the invented product names, demo codes (P15).
import { describe, expect, it } from "vitest";

import * as D from "@/api/decode";
import { check, fc } from "@/test/fc";
import { digits } from "@/test/arbitraries";

import {
  checkDigit,
  demoGtin13,
  demoRef,
  detectDemo,
  isDemoGtin,
  validGtin,
} from "./codes";
import { DemoClient, demoItems, type Fixture } from "./client";
import codesSvg from "./codes.svg.json";
import cologne from "./fixtures/cologne.json";
import istanbul from "./fixtures/istanbul.json";
import ohio from "./fixtures/ohio.json";

const fixtures = { istanbul, cologne, ohio } as unknown as Record<
  string,
  Fixture
>;
const ev = (f: Fixture) => {
  const r = D.decode(D.cascadeResult, f.evaluation);
  if (!r.ok) throw new Error(r.path);
  return r.value;
};

describe("7.1 Istanbul is the gate-1 case on real data", () => {
  const f = fixtures.istanbul!;
  const r = ev(f);
  it("finds PIPC row 5 probable, five months, from the amlodipine of the combination box", () => {
    const f5 = r.findings.find((x) => x.rule_id === "pipc:5")!;
    expect(f5.status).toBe("probable");
    expect(f5.months_between).toBe(5);
    expect(f5.index.items).toEqual([0]);
    expect(f5.index.matched_codes).toEqual(["C08CA01"]);
    expect(f5.integrity_codes).toContain("corrected_notice");
    expect(new Set(r.findings.map((x) => x.rule_id))).toEqual(
      new Set(["pipc:5", "pipc:6", "pipc:9", "pipc:12"]),
    );
    expect(r.item_warnings).toHaveLength(2);
    expect(r.rules.checked).toBe(63);
  });
  it("decomposes the combination box into amlodipine C08CA01 and lisinopril C09AA03", () => {
    const c = demoItems(f)[0]!.candidate;
    expect(c.kind).toBe("product");
    if (c.kind !== "product") return;
    expect(c.published_atc).toBe("C09BB03");
    expect(c.ingredients.map((i) => i.atc_codes.map((a) => a.code))).toEqual([
      ["C08CA01"],
      ["C09AA03"],
    ]);
    expect(
      c.ingredients.flatMap((i) => i.atc_codes.map((a) => a.code)),
    ).not.toContain("C09BB03");
  });
  it("records the Cologne and Ohio cases of the owner decision", () => {
    const c = ev(fixtures.cologne!);
    expect(c.findings.map((x) => [x.rule_id, x.form_confirmed])).toEqual([
      ["pipc:1", false],
      ["pipc:51", false],
    ]);
    const o = ev(fixtures.ohio!);
    expect(o.findings.map((x) => x.rule_id).sort()).toEqual([
      "pipc:24",
      "pipc:31",
    ]);
  });
});

describe("7.2 fixtures hold invented product names only and no token", () => {
  const PRODUCT_TEXT = [
    "product_name",
    "brand_name",
    "generic_name",
    "ingredient_text",
    "published_name",
  ];
  it.each(Object.entries(fixtures))("%s", (_, f) => {
    const allowed = new Set<string>();
    for (const it of f.items) {
      allowed.add(it.boxName);
      for (const c of (
        it.resolution as { candidates: Record<string, unknown>[] }
      ).candidates)
        for (const ing of (c.ingredients as
          Record<string, unknown>[] | undefined) ?? [])
          allowed.add(
            String(
              (ing.ingredient_key as { label_en?: string } | null)?.label_en ??
                "ingredient",
            ),
          );
    }
    const generic = new Set([
      "furosemide",
      "metformin",
      "atorvastatin",
      "paracetamol",
      "omeprazole",
      "sertraline",
      "lactulose",
      "alprazolam",
      "ramipril",
      "pantoprazole",
      "donepezil",
      "oxybutynin",
      "gabapentin",
      "amlodipine + lisinopril",
    ]);
    const walk = (v: unknown) => {
      if (Array.isArray(v)) v.forEach(walk);
      else if (v && typeof v === "object")
        for (const [k, x] of Object.entries(v)) {
          if (PRODUCT_TEXT.includes(k) && x !== null) {
            const s = String(x);
            expect(
              allowed.has(s) || generic.has(s) || /\((demo|Demo)\)/.test(s),
              `${k}: ${s}`,
            ).toBe(true);
          }
          if (k === "token" || k === "qr_url")
            throw new Error(`fixture stores ${k}`);
          walk(x);
        }
    };
    walk(f);
    expect(JSON.stringify(f)).not.toMatch(/AMLIPIN|8680199094206/i);
  });
});

describe("7.3 demo codes (P15)", () => {
  it("every demo code is a valid GTIN in 0295268… and resolves to its fixture item", () => {
    for (const [gtin, c] of Object.entries(
      codesSvg as Record<
        string,
        { patient: string; index: number; text: string }
      >,
    )) {
      expect(isDemoGtin(gtin)).toBe(true);
      expect(demoRef(gtin)).toEqual({ patient: c.patient, index: c.index });
      expect(detectDemo(c.text)).toEqual({
        patient: c.patient,
        index: c.index,
      });
      expect(fixtures[c.patient]!.items[c.index]!.demoCode).toBe(gtin);
    }
  });
  it("no real-prefix GTIN is a demo code", () => {
    const prefixes = [
      "868",
      "869",
      "03",
      "034",
      "084",
      "400",
      "420",
      "440",
      "50",
      "76",
    ];
    check(
      fc.property(fc.constantFrom(...prefixes), digits(12), (p, rest) => {
        const body = (p + rest).slice(0, 12);
        const gtin = body + checkDigit(body);
        expect(validGtin(gtin)).toBe(true);
        expect(isDemoGtin(gtin)).toBe(false);
        expect(isDemoGtin("0" + gtin)).toBe(false);
        expect(detectDemo(gtin)).toBeNull();
      }),
    );
  });
  it("detects demo codes on every input path before any request", async () => {
    let fetched = 0;
    const realFetch = globalThis.fetch;
    globalThis.fetch = (async () => {
      fetched++;
      throw new Error("no network in demo");
    }) as typeof fetch;
    try {
      check(
        fc.property(
          fc.integer({ min: 1, max: 9 }),
          fc.constantFrom("paren", "fnc1", "bare13", "bare14", "typed"),
          (n, form) => {
            const g = demoGtin13(n);
            const text = {
              paren: `(01)0${g}(17)281231(21)DEMO1`,
              fnc1: `]d201${"0" + g}17281231\x1d21DEMO1`,
              bare13: g,
              bare14: "0" + g,
              typed: g.replace(/(\d{4})/g, "$1 "),
            }[form];
            expect(detectDemo(text)).toEqual({
              patient: "istanbul",
              index: n - 1,
            });
          },
        ),
      );
      expect(detectDemo("NDC 0295-2682-01 DEMO")).toEqual({
        patient: "ohio",
        index: 2,
      });
      const client = new DemoClient(fixtures.istanbul!);
      const r = await client.resolveScan({ content: `(01)0${demoGtin13(2)}` });
      expect(r.ok).toBe(true);
      expect(fetched).toBe(0);
    } finally {
      globalThis.fetch = realFetch;
    }
  });
});

describe("DemoClient", () => {
  it("answers the recorded evaluation for the recorded input and has no write or loop route", async () => {
    const client = new DemoClient(fixtures.istanbul!);
    const r = await client.evaluate(client.recordedEvaluateIn());
    expect(r.ok).toBe(true);
    const other = await client.evaluate({
      ...client.recordedEvaluateIn(),
      items: [{ ingredient: "Q1" }],
    });
    expect(other.ok).toBe(false);
    for (const m of [
      "noteToken",
      "withdraw",
      "outcomeForm",
      "outcomes",
      "contribute",
      "deleteContribution",
    ])
      expect((client as unknown as Record<string, unknown>)[m]).toBeUndefined();
  });
});

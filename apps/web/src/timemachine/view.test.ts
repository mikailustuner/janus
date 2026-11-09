// Feature: experience Req 30 (time machine screens), properties P36–P40 (design §22).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import * as D from "@/api/decode";
import { parseCsv } from "@/report/csv.mjs";
import { check, fc } from "@/test/fc";
import vocabEn from "@/vocabulary/en.json";

import fixture from "./fixture.recorded.json";
import { cascadeOut, catalogue, substanceOut, type CascadeOut } from "./model";
import {
  englishShownFor,
  linearAxis,
  logAxis,
  patientTiming,
  place,
  reasonCode,
  shapeShown,
  TM_INDEX,
  type IndexEntry,
} from "./view";

const fx = fixture as unknown as {
  catalogue: unknown;
  substances: Record<string, unknown>;
  cascades: Record<string, unknown>;
};
const decodeOk = <T>(d: D.Decoder<T>, v: unknown): T => {
  const r = D.decode(d, v);
  if (!r.ok) throw new Error(r.path);
  return r.value;
};
const answers: CascadeOut[] = Object.values(fx.cascades).map((c) =>
  decodeOk(cascadeOut, c),
);

describe("recorded fixture", () => {
  it("decodes: catalogue, every substance, every cascade", () => {
    const cat = decodeOk(catalogue, fx.catalogue);
    expect(Object.keys(fx.substances).sort()).toEqual(
      [...cat.substance_ids].sort(),
    );
    expect(Object.keys(fx.cascades).sort()).toEqual(
      [...cat.cascade_ids].sort(),
    );
    for (const s of Object.values(fx.substances)) decodeOk(substanceOut, s);
    expect(cat.meta.review_status).toBe("AI-reviewed, pending expert review");
  });

  it("the index agrees with data/time_machine/cascades.csv and the vocabulary", () => {
    const [head, ...rows] = parseCsv(
      readFileSync(
        join(import.meta.dirname, "../../../../data/time_machine/cascades.csv"),
        "utf8",
      ),
    );
    const csv = rows
      .filter((r) => r.length === head!.length)
      .map((r) => Object.fromEntries(head!.map((h, i) => [h, r[i]!])));
    const names = vocabEn.ingredients as Record<string, string>;
    for (const e of TM_INDEX.cascades) {
      const row = csv.find((r) => r.cascade_id === e.id)!;
      expect(Number(row.pipc_position)).toBe(e.pipc_position);
      expect(e.index_keys.map((k) => names[k]!.toLowerCase())).toEqual(
        row.index_ingredients!.toLowerCase().split("|"),
      );
    }
  });

  it("today only the amlodipine cascade passes the patient gate (design §10.5)", () => {
    const passing = TM_INDEX.cascades.flatMap((e) =>
      e.index_keys.flatMap((k) =>
        patientTiming(e.pipc_position, k, answers) ? [e.id] : [],
      ),
    );
    expect([...new Set(passing)]).toEqual(["amlodipine_oedema_diuretic"]);
    expect(patientTiming(5, "Q411347", answers)).toEqual({
      start: 7,
      end: 104,
    });
  });
});

const caseArb = fc.record({
  small: fc.boolean(),
  agreement: fc.constantFrom(
    "agrees" as const,
    "disagrees" as const,
    "not_comparable" as const,
    null,
  ),
  hasOnset: fc.boolean(),
  start: fc.integer({ min: 0, max: 400 }),
  len: fc.integer({ min: 0, max: 400 }),
  row: fc.integer({ min: 1, max: 65 }),
  twins: fc.boolean(),
  keyMatches: fc.boolean(),
});

function build(c: {
  small: boolean;
  agreement: "agrees" | "disagrees" | "not_comparable" | null;
  hasOnset: boolean;
  start: number;
  len: number;
  row: number;
  twins: boolean;
  keyMatches: boolean;
}) {
  const base = answers.find(
    (a) => a.cascade.cascade_id === "amlodipine_oedema_diuretic",
  )!;
  const mk = (id: string): CascadeOut => ({
    ...base,
    cascade: {
      ...base.cascade,
      cascade_id: id,
      pipc_position: c.row,
      agreement: c.agreement,
      onset: c.hasOnset
        ? { ...base.cascade.onset!, small_sample: c.small }
        : null,
      middle_half_days: { start_days: c.start, end_days: c.start + c.len },
    },
  });
  const list = [mk("a"), ...(c.twins ? [mk("b")] : [])];
  const entries: IndexEntry[] = list.map((a) => ({
    id: a.cascade.cascade_id,
    pipc_position: c.row,
    index_keys: ["Q1"],
  }));
  return { list, entries, key: c.keyMatches ? "Q1" : "Q2" };
}

describe("patient gate (P36)", () => {
  it("P36: the sentence appears iff one matching cascade, not a small sample, agreement 'agrees'; it carries the middle half", () => {
    check(
      fc.property(caseArb, (c) => {
        const { list, entries, key } = build(c);
        const out = patientTiming(c.row, key, list, entries);
        const expected =
          !c.twins &&
          c.keyMatches &&
          c.hasOnset &&
          !c.small &&
          c.agreement === "agrees";
        expect(out !== null).toBe(expected);
        if (out) expect(out).toEqual({ start: c.start, end: c.start + c.len });
        // Another row never shows it.
        expect(patientTiming(c.row + 100, key, list, entries)).toBeNull();
      }),
    );
  });

  it("P37: the shape class is never named for a small sample", () => {
    for (const a of answers)
      if (a.cascade.onset?.small_sample)
        expect(shapeShown(a.cascade)).toBe(false);
  });
});

describe("texts (P38)", () => {
  it("P38: no English source text with the word PBPK is shown for a compartmental model", () => {
    check(
      fc.property(fc.string(), fc.boolean(), (text, withWord) => {
        const t = withWord ? `${text} (not PBPK)` : text.replace(/pbpk/gi, "");
        const shown = englishShownFor("compartmental", t);
        if (shown !== null) expect(shown.toLowerCase()).not.toContain("pbpk");
        expect(englishShownFor("pbpk", t)).toBe(t);
      }),
    );
  });

  it("maps the API's fixed reasons to codes, and nothing else", () => {
    expect(
      reasonCode("no published human PK parameters for this constituent"),
    ).toEqual({ code: "no_pk" });
    expect(
      reasonCode("model failed the credibility rule for this drug"),
    ).toEqual({ code: "failed_credibility" });
    expect(reasonCode("fewer than 10 reports with a usable interval")).toEqual({
      code: "few_reports",
      n: 10,
    });
    expect(reasonCode("something new")).toBeNull();
    expect(reasonCode("")).toBeNull();
    for (const s of Object.values(fx.substances)) {
      const o = decodeOk(substanceOut, s);
      for (const e of o.exposure) {
        if (e.not_validated_reason)
          expect(reasonCode(e.not_validated_reason)).not.toBeNull();
        if (e.no_potency_reason)
          expect(reasonCode(e.no_potency_reason)).not.toBeNull();
      }
    }
  });
});

describe("axes (P39)", () => {
  it("P39: every value is placed inside [0, 1] and order is kept", () => {
    check(
      fc.property(
        fc.array(fc.double({ min: 1e-6, max: 1e6, noNaN: true }), {
          minLength: 2,
          maxLength: 8,
        }),
        (vs) => {
          for (const axis of [logAxis(vs), linearAxis(vs)]) {
            const ps = vs.map((v) => place(axis, v));
            for (const p of ps) {
              expect(p).toBeGreaterThanOrEqual(0);
              expect(p).toBeLessThanOrEqual(1);
            }
            const sorted = [...vs].sort((a, b) => a - b);
            const placed = sorted.map((v) => place(axis, v));
            for (let i = 1; i < placed.length; i++)
              expect(placed[i]!).toBeGreaterThanOrEqual(placed[i - 1]! - 1e-12);
          }
        },
      ),
    );
  });

  it("P39: a linear axis covers its maximum; a log axis covers every value within 8 decades", () => {
    check(
      fc.property(
        fc.array(fc.double({ min: 0.001, max: 1e4, noNaN: true }), {
          minLength: 1,
          maxLength: 8,
        }),
        (vs) => {
          expect(linearAxis(vs).max).toBeGreaterThanOrEqual(Math.max(...vs));
          const l = logAxis(vs);
          expect(l.max).toBeGreaterThanOrEqual(Math.max(...vs) * 0.999999);
        },
      ),
    );
  });
});

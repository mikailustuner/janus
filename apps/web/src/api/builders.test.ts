// Feature: experience, Property P2 (builders part): request bodies hold exactly the route model's
// fields, satisfy its patterns, and carry no box name, ATC code, binary, `demo` key or token
// outside the loop routes (Req 23.1, 23.2, 4.3).
import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";
import {
  ATC_SHAPE,
  candidateId,
  eventKey,
  hex64,
  month,
  qid,
  sentinelBoxName,
  walk,
} from "@/test/arbitraries";

import * as B from "./builders";

const tokenArb = fc
  .array(fc.constantFrom(..."ABCabc012_-"), { minLength: 40, maxLength: 120 })
  .map((a) => a.join(""));

const itemArb = fc.record({
  kind: fc.constantFrom("product", "ingredient"),
  product: candidateId,
  ingredient: qid,
  choices: fc.uniqueArray(
    fc.record({ position: fc.integer({ min: 0, max: 49 }), ingredient: qid }),
    {
      selector: (c) => c.position,
      maxLength: 3,
    },
  ),
  started: fc.option(month, { nil: null }),
  boxName: sentinelBoxName,
});

function bodyHasNoForbiddenContent(body: unknown, boxNames: readonly string[]) {
  const { keys, strings } = walk(body);
  expect(keys).not.toContain("demo");
  for (const s of strings) {
    for (const name of boxNames) expect(s.includes(name)).toBe(false);
    expect(ATC_SHAPE.test(s), s).toBe(false);
  }
  expect(JSON.stringify(body)).not.toMatch(/Blob|ArrayBuffer/);
}

describe("evaluation and note bodies", () => {
  it("have exactly the model keys and never a box name or ATC code", () => {
    check(
      fc.property(
        hex64,
        fc.array(itemArb, { minLength: 1, maxLength: 50 }),
        (dv, items) => {
          const built = items.map((i) =>
            B.itemIn(
              i.kind === "product"
                ? { product: i.product, choices: i.choices, started: i.started }
                : { ingredient: i.ingredient, started: i.started },
            ),
          );
          const body = B.evaluateBody(dv, built);
          expect(Object.keys(body).sort()).toEqual([
            "dataset_version",
            "items",
          ]);
          body.items.forEach((item, n) => {
            const src = items[n]!;
            for (const k of Object.keys(item))
              expect(["product", "ingredient", "choices", "started"]).toContain(
                k,
              );
            expect("product" in item !== "ingredient" in item).toBe(true);
            if (item.choices) expect(item.product).toBeDefined();
            if (src.started === null) expect(item.started).toBeUndefined();
            else expect(item.started).toMatch(B.PATTERNS.month);
          });
          const note = B.noteBody(body, {}, ["tr", "en"], "TR", null);
          expect(Object.keys(note).sort()).toEqual([
            "evaluation",
            "languages",
            "pins",
            "region",
          ]);
          bodyHasNoForbiddenContent(
            note,
            items.map((i) => i.boxName),
          );
        },
      ),
    );
  });

  it("refuse an item with both or neither kind, choices without a product, a bad month", () => {
    expect(() =>
      B.itemIn({ product: "TR:titck:1", ingredient: "Q1", started: null }),
    ).toThrow(B.BuildError);
    expect(() => B.itemIn({ started: null })).toThrow(B.BuildError);
    expect(() =>
      B.itemIn({
        ingredient: "Q1",
        choices: [{ position: 0, ingredient: "Q2" }],
        started: null,
      }),
    ).toThrow(B.BuildError);
    expect(() => B.itemIn({ ingredient: "Q1", started: "2024-13" })).toThrow(
      B.BuildError,
    );
    expect(() => B.itemIn({ ingredient: "C08CA01", started: null })).toThrow(
      B.BuildError,
    );
    expect(() =>
      B.evaluateBody("abc", [B.itemIn({ ingredient: "Q1", started: null })]),
    ).toThrow(B.BuildError);
  });
});

describe("memory bodies", () => {
  it("carry distinct keys and the route fields only", () => {
    check(
      fc.property(
        fc.uniqueArray(qid, { minLength: 2, maxLength: 20 }),
        eventKey,
        (keys, ev) => {
          expect(Object.keys(B.combinationBody(keys))).toEqual(["ingredients"]);
          expect(Object.keys(B.regionsBody(keys, ev)).sort()).toEqual([
            "event",
            "ingredients",
          ]);
          expect(B.pairBody(keys[0]!, ev)).toEqual({
            ingredient: keys[0],
            event: { key: ev },
            region: "ALL",
            scope: "suspect",
          });
          expect(
            Object.keys(B.sharedBody("outcomes", keys, ev, "adverse")).sort(),
          ).toEqual(["direction", "event", "ingredients", "layer"]);
          bodyHasNoForbiddenContent(B.combinationBody(keys), []);
        },
      ),
    );
    expect(() => B.combinationBody(["Q1"])).toThrow(B.BuildError);
    expect(() => B.combinationBody(["Q1", "Q1"])).toThrow(B.BuildError);
  });
});

describe("loop and donation bodies", () => {
  it("put the token only in the bodies of the loop routes", () => {
    check(
      fc.property(tokenArb, hex64, (token, dv) => {
        expect(B.tokenOnlyBody(token)).toEqual({ token });
        const out = B.outcomesBody(token, [
          {
            ref: 0,
            assessment: "confirmed",
            action: "stopped",
            action_on: "index",
          },
          { ref: 1, assessment: "not_a_cascade" },
        ]);
        expect(Object.keys(out).sort()).toEqual(["answers", "token"]);
        // No other body has a token field or the token value.
        const ev = B.evaluateBody(dv, [
          B.itemIn({ ingredient: "Q1", started: null }),
        ]);
        const others = [
          ev,
          B.noteBody(ev, {}, ["en"], "US", "US"),
          B.tokenBody(
            B.noteBody(ev, {}, ["en"], "US", null),
            "2026-11-v1",
            "US",
          ),
          B.searchBody("amlodipine", "TR"),
          B.scanBody("(01)08680000000000", null),
        ];
        for (const b of others) {
          const { keys, strings } = walk(b);
          expect(keys).not.toContain("token");
          expect(strings).not.toContain(token);
        }
      }),
    );
  });

  it("require action_on exactly for dose, medicine and stop actions", () => {
    const t = "A".repeat(40);
    expect(() =>
      B.outcomesBody(t, [
        { ref: 0, assessment: "confirmed", action: "stopped" },
      ]),
    ).toThrow(B.BuildError);
    expect(() =>
      B.outcomesBody(t, [
        {
          ref: 0,
          assessment: "confirmed",
          action: "no_change",
          action_on: "index",
        },
      ]),
    ).toThrow(B.BuildError);
    expect(() =>
      B.outcomesBody(t, [
        { ref: 0, assessment: "confirmed" },
        { ref: 0, assessment: "not_a_cascade" },
      ]),
    ).toThrow(B.BuildError);
  });

  it("build a donation only with the consent ticked and the allowed fields", () => {
    check(
      fc.property(
        fc.constantFrom(...B.AGE_BANDS),
        fc.constantFrom("female" as const, "male" as const, null),
        fc.constantFrom("TR" as const, "EU" as const, "US" as const),
        fc.uniqueArray(qid, { minLength: 1, maxLength: 20 }),
        (ageBand, sex, region, ingredients) => {
          const form = {
            consentVersion: "2026-11-v1",
            consentTicked: true,
            ageBand,
            sex,
            region,
            ingredients,
            event: "cough",
            direction: "adverse" as const,
          };
          const body = B.contributionBody(form);
          expect(body.consent).toEqual({
            version: "2026-11-v1",
            explicit: true,
          });
          for (const k of Object.keys(body))
            expect([
              "consent",
              "age_band",
              "sex",
              "region",
              "ingredients",
              "event",
              "direction",
            ]).toContain(k);
          expect("sex" in body).toBe(sex !== null);
          expect(() =>
            B.contributionBody({ ...form, consentTicked: false }),
          ).toThrow(B.BuildError);
          expect(() => B.contributionBody({ ...form, ageBand: 15 })).toThrow(
            B.BuildError,
          );
        },
      ),
    );
  });
});

describe("resolution bodies", () => {
  it("trim the query, keep 2-100 characters and send the region only when set", () => {
    check(
      fc.property(
        fc.string({ minLength: 2, maxLength: 100 }),
        fc.constantFrom("TR" as const, null),
        (q, r) => {
          const trimmed = q.trim();
          if (trimmed.length < 2) {
            expect(() => B.searchBody(q, r)).toThrow(B.BuildError);
            return;
          }
          const body = B.searchBody(q, r);
          expect(body.query).toBe(trimmed);
          expect("region" in body).toBe(r !== null);
        },
      ),
    );
    expect(() => B.productsBody(["C08CA01"])).toThrow(B.BuildError);
    expect(B.scanBody("08680199094206", "TR")).toEqual({
      content: "08680199094206",
      region: "TR",
    });
  });
});

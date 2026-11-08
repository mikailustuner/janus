// Feature: experience, Properties P21 (confirm view model) and P5 (re-resolution).
import { describe, expect, it } from "vitest";

import type { Candidate, ResolutionResult } from "@/api/contracts";
import * as D from "@/api/decode";
import { check, fc } from "@/test/fc";
import { FIXTURES } from "@/test/results";
import type { Item } from "@/store/list";

import { confirmView } from "./confirm";
import { equivalents, reresolve } from "./reresolve";

const decode = (v: unknown) => {
  const r = D.decode(D.resolutionResult, v);
  if (!r.ok) throw new Error(r.path);
  return r.value;
};
const RESOLUTIONS: ResolutionResult[] = FIXTURES.flatMap((f) =>
  f.items.map((i) => decode(i.resolution)),
);
const CANDIDATES: Candidate[] = RESOLUTIONS.flatMap((r) => r.candidates);

const resolutionArb = fc
  .record({
    base: fc.constantFrom(...RESOLUTIONS),
    candidates: fc.array(fc.constantFrom(...CANDIDATES), { maxLength: 6 }),
    notices: fc.subarray([
      "source_may_be_outdated",
      "region_adapter_not_available",
      "unmapped_ingredients",
      "unknown_candidate_ids",
      "no_open_product_database",
    ] as const),
    matched: fc.constantFrom("barcode", "ntin_digits", "ai_712", "name"),
    homeopathic: fc.boolean(),
  })
  .map(
    ({
      base,
      candidates,
      notices,
      matched,
      homeopathic,
    }): ResolutionResult => ({
      ...base,
      candidates: candidates.map((c) =>
        c.kind === "product"
          ? { ...c, matched_by: matched as never, homeopathic }
          : c,
      ),
      notices: notices.map((code) => ({
        code,
        region: "EU",
        country: code === "no_open_product_database" ? "DE" : null,
        source_id: null,
        date: null,
      })),
    }),
  );

describe("P21 confirm view model", () => {
  it("never preselects, keeps not-found apart from no-open-database, labels digits matches", () => {
    check(
      fc.property(resolutionArb, (r) => {
        const v = confirmView(r);
        if (r.candidates.length === 0) {
          if (r.notices.some((n) => n.code === "no_open_product_database"))
            expect(v.kind).toBe("no_open_database");
          else if (
            r.notices.some((n) => n.code === "region_adapter_not_available")
          )
            expect(v.kind).toBe("not_supported");
          else {
            expect(v.kind).toBe("not_found");
            if (v.kind === "not_found")
              expect(v.sources.map((s) => s.sourceId)).toEqual(
                r.sources.map((s) => s.source_id),
              );
          }
          return;
        }
        expect(v.kind).toBe("candidates");
        if (v.kind !== "candidates") return;
        expect(v.cards).toHaveLength(r.candidates.length);
        expect(Object.keys(v)).not.toContain("selected");
        for (const card of v.cards) {
          const c = card.candidate;
          expect(card.attribution.sourceId).toBe(c.source.source_id);
          if (c.kind === "product") {
            expect(card.digitsNote).toBe(
              c.matched_by === "ntin_digits" || c.matched_by === "ai_712",
            );
            expect(card.homeopathic).toBe(c.homeopathic);
            expect(card.publishedAtc).toBe(c.published_atc);
            // the product's published code is never listed as an ingredient code
            if (c.ingredients.length > 1 && c.published_atc)
              expect(card.ingredientCodes).not.toContain(c.published_atc);
            expect(card.ambiguous.map((a) => a.position)).toEqual(
              c.ingredients
                .filter((g) => g.status === "ambiguous")
                .map((g) => g.position),
            );
          }
        }
        expect(v.notices).not.toContain("no_open_product_database");
      }),
    );
  });
  it("words the Spanish machine status strings and keeps numeric codes as published", () => {
    const c = CANDIDATES.find((x) => x.kind === "product")!;
    const r = {
      ...RESOLUTIONS[0]!,
      candidates: [
        {
          ...c,
          country: "ES" as const,
          status_published: [
            "commercialised:true",
            "registration_status:1 2010-01-01",
            "odd",
          ],
        },
      ],
    };
    const v = confirmView(r as ResolutionResult);
    if (v.kind !== "candidates") throw new Error();
    expect(v.cards[0]!.status).toEqual([
      { kind: "es", code: "commercialised_true" },
      { kind: "es", code: "registration", value: "1", date: "2010-01-01" },
      { kind: "es", code: "raw", value: "odd" },
    ]);
  });
});

const itemOf = (c: Candidate, i: number): Item => ({
  id: `i${i}`,
  sourceKey:
    c.kind === "ingredient"
      ? {
          kind: "search",
          query: "q",
          region: null,
          pick: { kind: "ingredient", qid: c.ingredient_key.qid },
        }
      : { kind: "scan", content: `(01)0${i}` },
  datasetVersion: "a".repeat(64),
  candidate: c,
  choices: [{ position: 0, ingredient: "Q1" }],
  started: i % 2 ? "2024-01" : null,
  boxName: `Box ${i}`,
  needsConfirmation: false,
});

describe("P5 re-resolution", () => {
  it("replaces an item only by a unique equivalent, keeps start and box name, never mixes versions", async () => {
    await check(
      fc.asyncProperty(
        fc.array(fc.constantFrom(...CANDIDATES), {
          minLength: 1,
          maxLength: 8,
        }),
        fc.array(fc.constantFrom(0, 1, 2), { minLength: 8, maxLength: 8 }),
        fc.constantFrom("b".repeat(64), "c".repeat(64)),
        async (cands, answers, newVersion) => {
          const items = cands.map(itemOf);
          let calls = 0;
          const resolve = async (k: Item["sourceKey"]) => {
            const i = calls++;
            const item = items[i]!;
            const n = answers[i]!;
            const res: ResolutionResult = {
              ...RESOLUTIONS[0]!,
              dataset_version: newVersion,
              candidates: Array.from({ length: n }, () => item.candidate),
            };
            void k;
            return { ok: true as const, data: res };
          };
          const out = await reresolve(items, resolve);
          expect(calls).toBe(items.length);
          out.forEach((o, i) => {
            expect(o.started).toBe(items[i]!.started);
            expect(o.boxName).toBe(items[i]!.boxName);
            if (answers[i] === 1) {
              expect(o.needsConfirmation).toBe(false);
              expect(o.datasetVersion).toBe(newVersion);
            } else expect(o.needsConfirmation).toBe(true);
            if (!o.needsConfirmation)
              for (const ch of o.choices) {
                const c = o.candidate;
                expect(
                  c.kind === "product" &&
                    c.ingredients
                      .find((g) => g.position === ch.position)
                      ?.key_candidates.includes(ch.ingredient),
                ).toBe(true);
              }
          });
          const versions = new Set(
            out
              .filter((o) => !o.needsConfirmation)
              .map((o) => o.datasetVersion),
          );
          expect(versions.size).toBeLessThanOrEqual(1);
        },
      ),
    );
  });
  it("a search item is equivalent only to the same ingredient or the same product name and source", () => {
    const ing = CANDIDATES.find((c) => c.kind === "ingredient")!;
    const item = itemOf(ing, 0);
    expect(
      equivalents(item, {
        ...RESOLUTIONS[0]!,
        candidates: [ing, ...CANDIDATES.filter((c) => c.kind === "product")],
      }),
    ).toEqual([ing]);
  });
});

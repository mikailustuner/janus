// Feature: séance view (séance design §7): decoders on synthetic answers (src/test/fixtures/seance.ts;
// the recorded file is checked in src/test/recorded-contract.test.ts), the
// demo client (no network), the picker's choices, the three seats in fixed order, the cross-
// reference from a hypothesis card (never a different exposure), and the localised vocabularies.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { decode } from "@/api/decode";
import { routing } from "@/i18n/routing";
import { check, fc } from "@/test/fc";
import { seanceSet } from "@/test/fixtures/seance";

import { demoSeance, type SeanceFixture } from "./client";
import {
  CONDITIONS,
  HEADLINE_REASONS,
  INTEGRITY,
  MISSING,
  PRESENT_CODES,
  STUDY_TYPES,
  WITNESSES,
  catalogueOut,
  seanceOut,
  type CatalogueOut,
  type PairSummary,
  type SeanceOut,
} from "./model";
import {
  FEATURED,
  choices,
  crossLinks,
  doiUrl,
  initialPair,
  locatorValues,
  missingInOrder,
  seats,
  showableTitle,
  withSubstance,
} from "./view";

const fx = seanceSet() as unknown as SeanceFixture;
const cat = fx.catalogue as CatalogueOut;
const answers = fx.pairs.map((p) => p.answer as SeanceOut);

type Tree = { [k: string]: string | Tree };
const messages = Object.fromEntries(
  routing.locales.map((l) => [
    l,
    JSON.parse(
      readFileSync(
        join(import.meta.dirname, "../../messages", `${l}.json`),
        "utf8",
      ),
    ) as Tree,
  ]),
);
const has = (tree: Tree, key: string) => {
  let node: string | Tree | undefined = tree;
  for (const part of key.split("."))
    node = typeof node === "object" ? node[part] : undefined;
  return typeof node === "string" && node.trim() !== "";
};

afterEach(() => vi.unstubAllGlobals());

describe("answers", () => {
  it("decode with the contract decoders", () => {
    expect(decode(catalogueOut, fx.catalogue).ok).toBe(true);
    for (const a of answers) expect(decode(seanceOut, a).ok).toBe(true);
  });

  it("are the two headline pairs at two of three witnesses, present missing", () => {
    expect(fx.pairs.map((p) => p.request)).toEqual([
      { substance: "st_johns_wort", condition: "wound" },
      { substance: "vinegar", condition: "infection" },
    ]);
    for (const a of answers) {
      expect(a.headline.eligible).toBe(true);
      expect(a.supporting_witnesses).toBe(2);
      expect(a.missing_witnesses).toEqual(["present"]);
      expect(a.substance.identification_label).toBe("identified");
      for (const i of a.witnesses.past.items) {
        expect(i.translation_kind).toBe("machine_translation");
        expect(i.expert_review).toBe("pending");
      }
    }
  });

  it("refuse an answer with a wrong or missing field", () => {
    const base = answers[0] as unknown as Record<string, unknown>;
    check(
      fc.property(
        fc.constantFrom(
          "substance",
          "witnesses",
          "supporting_witnesses",
          "missing_witnesses",
          "framing",
          "headline",
          "disclaimer",
        ),
        fc.constantFrom(null, undefined, 7, [3]),
        (key, junk) => {
          expect(decode(seanceOut, { ...base, [key]: junk }).ok).toBe(false);
        },
      ),
    );
  });
});

describe("demo client", () => {
  it("answers the given pairs and the catalogue without any request", async () => {
    const fetchSpy = vi.fn(() => {
      throw new Error("no network in demo mode");
    });
    vi.stubGlobal("fetch", fetchSpy);
    const c = demoSeance(fx);
    const catR = await c.catalogue();
    expect(catR.ok).toBe(true);
    for (const p of fx.pairs) {
      const r = await c.pair(p.request);
      expect(r.ok && r.data.substance.id).toBe(p.request.substance);
    }
    const miss = await c.pair({ substance: "honey", condition: "burn" });
    expect(miss.ok).toBe(false);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("offers only the given pairs in the picker", () => {
    const c = demoSeance(fx);
    const list = choices(cat, c.only);
    expect(
      list.flatMap((x) => x.pairs.map((p) => [p.substance, p.condition])),
    ).toEqual([
      ["st_johns_wort", "wound"],
      ["vinegar", "infection"],
    ]);
  });
});

const pairArb = (ids: string[]): fc.Arbitrary<PairSummary> =>
  fc.record({
    substance: fc.constantFrom(...ids),
    condition: fc.constantFrom(...CONDITIONS),
    past_passages: fc.nat(5),
    science_studies: fc.nat(3),
    present_link: fc.constantFrom("same", "component", "different", "none"),
    present_ingredient_key: fc.constantFrom("Q47512", "Q2314", "Q1"),
  }) as fc.Arbitrary<PairSummary>;
const ids = cat.substances.map((s) => s.id);
const catArb = fc
  .uniqueArray(pairArb(ids), {
    selector: (p) => `${p.substance}/${p.condition}`,
    maxLength: 40,
  })
  .map((pairs) => ({ ...cat, pairs }));

describe("choices", () => {
  it("lists every pair once, by substance, conditions in fixed order", () => {
    check(
      fc.property(catArb, (c) => {
        const list = choices(c);
        const flat = list.flatMap((x) => x.pairs);
        expect(flat).toHaveLength(c.pairs.length);
        for (const x of list) {
          expect(x.pairs.every((p) => p.substance === x.substance.id)).toBe(
            true,
          );
          const order = x.pairs.map((p) => CONDITIONS.indexOf(p.condition));
          expect(order).toEqual([...order].sort((a, b) => a - b));
        }
      }),
    );
  });

  it("opens the wanted pair only when it is listed, else a featured one, else the first", () => {
    check(
      fc.property(
        catArb,
        fc.constantFrom(...ids),
        fc.constantFrom(...CONDITIONS),
        (c, substance, condition) => {
          const list = choices(c);
          const got = initialPair(list, { substance, condition });
          const listed = c.pairs.some(
            (p) => p.substance === substance && p.condition === condition,
          );
          const all = list.flatMap((x) => x.pairs);
          const featured = FEATURED.find((f) =>
            all.some(
              (p) => p.substance === f.substance && p.condition === f.condition,
            ),
          );
          const fallback = featured ?? all[0];
          if (listed) expect(got).toEqual({ substance, condition });
          else if (fallback)
            expect(got).toEqual({
              substance: fallback.substance,
              condition: fallback.condition,
            });
          else expect(got).toBeNull();
          const next = withSubstance(list, substance, condition);
          if (next)
            expect(
              c.pairs.some(
                (p) =>
                  p.substance === next.substance &&
                  p.condition === next.condition,
              ),
            ).toBe(true);
        },
      ),
    );
  });
});

describe("first pair of the catalogue", () => {
  it("is St John's wort / wound", () => {
    expect(initialPair(choices(cat), null)).toEqual({
      substance: "st_johns_wort",
      condition: "wound",
    });
  });
});

describe("cross-reference from a hypothesis card", () => {
  it("offers exactly the same-exposure and component pairs of that ingredient", () => {
    check(
      fc.property(
        catArb,
        fc.constantFrom("Q47512", "Q2314", "Q1", "Q9"),
        (c, key) => {
          const got = crossLinks(c, key).flatMap((l) => l.pairs);
          const want = c.pairs.filter(
            (p) =>
              p.present_ingredient_key === key &&
              (p.present_link === "same" || p.present_link === "component"),
          );
          expect(new Set(got)).toEqual(new Set(want));
          expect(
            got.some(
              (p) =>
                p.present_link === "different" || p.present_link === "none",
            ),
          ).toBe(false);
        },
      ),
    );
  });

  it("links acetic acid to vinegar and never sodium chloride to salt", () => {
    expect(crossLinks(cat, "Q47512").map((l) => l.substance.id)).toEqual([
      "vinegar",
    ]);
    expect(crossLinks(cat, "Q2314")).toEqual([]);
  });
});

describe("seats", () => {
  const witnessArb = fc.record({
    past: fc.boolean(),
    present: fc.boolean(),
    science: fc.boolean(),
  });
  it("are always the three witnesses in order past, present, science", () => {
    check(
      fc.property(fc.constantFrom(...answers), witnessArb, (a, keep) => {
        const missing = WITNESSES.filter((w) => !keep[w]);
        const out = { ...a, missing_witnesses: [...missing].reverse() };
        expect(seats(out).map((s) => s.name)).toEqual([...WITNESSES]);
        expect(missingInOrder(out)).toEqual(missing);
      }),
    );
  });

  it("give the locator of every passage with a short entry id", () => {
    for (const a of answers)
      for (const i of a.witnesses.past.items) {
        const l = locatorValues(i);
        expect(l.entry).toMatch(/^h\d{4}$/);
        expect(l.start).toBeLessThanOrEqual(l.end);
      }
  });

  it("withhold a paper title with a forbidden phrase, keep the others", () => {
    expect(showableTitle("Honey as a topical treatment for wounds")).toBe(
      false,
    );
    for (const a of answers)
      for (const i of a.witnesses.science.items)
        expect(showableTitle(i.title)).toBe(true);
  });

  it("link a DOI through the resolver", () => {
    expect(doiUrl("10.1371/journal.pone.0136190")).toBe(
      "https://doi.org/10.1371/journal.pone.0136190",
    );
  });
});

describe("vocabularies", () => {
  const keys = [
    ...MISSING.map((c) => `Seance.missingReason.${c}`),
    ...PRESENT_CODES.map((c) => `Seance.codes.${c}`),
    ...STUDY_TYPES.map((c) => `Seance.science.studyType.${c}`),
    ...INTEGRITY.map((c) => `Seance.science.integrity.${c}`),
    ...HEADLINE_REASONS.map((c) => `Seance.headline.reason.${c}`),
    ...CONDITIONS.map((c) => `Seance.condition.${c}`),
    ...["none", "low", "moderate"].map((c) => `Seance.confidence.${c}`),
    ...["toxic", "caustic"].map((c) => `Seance.substance.hazard.${c}`),
    ...WITNESSES.flatMap((w) => [
      `Seance.seat.${w}.title`,
      `Seance.witness.${w}`,
    ]),
    "Seance.substance.identified",
    "Seance.substance.uncertain",
    "Seance.past.mt",
    "Seance.past.aiReviewed",
    "Seance.framing",
    "Seance.review",
    "Research.review",
  ];
  it.each(routing.locales)("every code has a message in %s", (locale) => {
    for (const k of keys) expect(has(messages[locale]!, k), k).toBe(true);
  });

  it("every present code of the answers is a known code", () => {
    expect(answers.some((a) => a.witnesses.present.codes.length > 0)).toBe(
      true,
    );
    for (const a of answers)
      for (const c of a.witnesses.present.codes)
        expect(PRESENT_CODES as readonly string[]).toContain(c);
  });
});

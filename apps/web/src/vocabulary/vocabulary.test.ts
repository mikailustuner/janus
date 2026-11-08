// Feature: experience, Property P13: the committed vocabulary equals the generator output from
// the API's reviewed files, and `ingredientName` follows doctor-loop DP16 exactly (Req 2.5).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";
import { qid } from "@/test/arbitraries";

import {
  generate,
  LOCALES,
  parseCsv,
  serialise,
} from "../../scripts/gen-vocabulary.mjs";

import {
  eventKeyForRule,
  ingredientName,
  type Loaded,
  type Vocabulary,
  type VocabularyIndex,
} from "./index";

const repoRoot = join(import.meta.dirname, "../../../..");
const committed = (name: string) =>
  readFileSync(join(import.meta.dirname, name), "utf8");

describe("generated vocabulary", () => {
  it("equals the generator output (run `pnpm gen:vocabulary` after a glossary change)", () => {
    const files = generate(repoRoot) as unknown as Record<string, unknown>;
    for (const [name, value] of Object.entries(files))
      expect(committed(name), name).toBe(serialise(value));
  });

  it("keeps only accepted glossary rows and active event rows", () => {
    const rows = parseCsv(
      readFileSync(
        join(repoRoot, "apps/api/janus/notes/glossary/ingredients.csv"),
        "utf8",
      ),
    ) as Record<string, string>[];
    const rejected = rows
      .filter((r) => r.status !== "accepted")
      .map((r) => r.key);
    const index = JSON.parse(committed("index.json")) as VocabularyIndex;
    for (const key of rejected)
      expect(index.english_names[key!]).toBeUndefined();
    const en = JSON.parse(committed("en.json")) as Vocabulary;
    expect(en.cascades["5"]).toMatchObject({
      drug_a: "Calcium channel blocker",
      drug_b: "Diuretic",
    });
    expect(Object.keys(en.cascades)).toHaveLength(65);
  });

  it("parses quoted CSV fields", () => {
    expect(parseCsv('a,b\n"x, ""y""",z\n')).toEqual([{ a: 'x, "y"', b: "z" }]);
  });
});

describe("ingredientName (doctor-loop DP16)", () => {
  const sentences = {
    "name.not_translated": "NT",
    "name.not_reviewed": "NR",
  };
  const arb = fc.record({
    key: qid,
    own: fc.option(fc.string({ minLength: 1 }), { nil: undefined }),
    en: fc.option(fc.string({ minLength: 1 }), { nil: undefined }),
    label: fc.option(fc.string({ minLength: 1 }), { nil: null }),
    locale: fc.constantFrom(...(LOCALES as string[])),
  });
  it("prefers the reviewed name, then the English INN, then the unreviewed label, then the code", () => {
    check(
      fc.property(arb, ({ key, own, en, label, locale }) => {
        const v: Loaded = {
          locale: locale as Loaded["locale"],
          vocab: {
            events: {},
            cascades: {},
            ingredients: own ? { [key]: own } : {},
            sentences,
          },
          index: { sources: {}, english_names: en ? { [key]: en } : {} },
        };
        const n = ingredientName(v, key, label);
        if (own) expect(n).toEqual({ text: own, basis: "glossary", tag: null });
        else if (en)
          expect(n).toEqual({ text: en, basis: "english_fallback", tag: "NT" });
        else if (label)
          expect(n).toEqual({ text: label, basis: "not_reviewed", tag: "NR" });
        else expect(n).toEqual({ text: null, basis: "code_only", tag: "NR" });
      }),
    );
  });

  it("finds the event key of a rule from pipc_positions when it is unique", () => {
    const en = JSON.parse(committed("en.json")) as Vocabulary;
    const v: Loaded = {
      locale: "en",
      vocab: en,
      index: { sources: {}, english_names: {} },
    };
    expect(eventKeyForRule(v, "pipc:1")).toBe("cough");
    expect(eventKeyForRule(v, "pipc:5")).toBe("peripheral_oedema");
    expect(eventKeyForRule(v, "nonsense")).toBeNull();
  });
});

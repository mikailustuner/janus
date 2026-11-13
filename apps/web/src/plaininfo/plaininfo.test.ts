// Feature: plain-medicine-info, web properties W1–W3 (design §7). Validates Req 4, 5.3, 5.8,
// 5.9, 6.2, 6.3: the request holds only codes and the product's own code or published name;
// the decoder accepts the API's answers and refuses changed ones; demo mode answers from the
// recorded-shaped file (synthetic, src/test/fixtures/plaininfo.ts; the recorded file itself is
// checked in src/test/recorded-contract.test.ts); every PlainInfo text exists in five languages
// within the word rules.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { createTranslator } from "next-intl";
import { describe, expect, it } from "vitest";

import type { Candidate, Locale } from "@/api/contracts";
import { decode } from "@/api/decode";
import { messageKeyFor } from "@/api/errors";
import { demoItems, type Fixture } from "@/demo/client";
import cologne from "@/demo/fixtures/cologne.json";
import istanbul from "@/demo/fixtures/istanbul.json";
import ohio from "@/demo/fixtures/ohio.json";
import { routing } from "@/i18n/routing";
import type { Item } from "@/store/list";
import { check, fc } from "@/test/fc";
import { plainInfoRecorded } from "@/test/fixtures/plaininfo";
import { violations } from "@/test/plaininfo-words";
import type { Loaded, Vocabulary, VocabularyIndex } from "@/vocabulary";
import index from "@/vocabulary/index.json";

import { recordedCall } from "./client";
import { medicineInfoOut, type MedicineInfoOut } from "./model";
import { codesOf, infoQuery, productOf, queryKey } from "./query";

type Tree = { [key: string]: string | Tree };
const read = (path: string) =>
  JSON.parse(readFileSync(join(import.meta.dirname, path), "utf8"));
const LOCALES = routing.locales as readonly Locale[];
const catalogues = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../../messages/${l}.json`) as Tree]),
) as Record<Locale, Tree>;
const vocab = (l: Locale): Loaded => ({
  locale: l,
  vocab: read(`../vocabulary/${l}.json`) as Vocabulary,
  index: index as VocabularyIndex,
});
const en = vocab("en");
const answers = read("fixtures/info.json") as Record<string, unknown>;

const fixtures = [istanbul, ohio, cologne] as unknown as Fixture[];
const items: Item[] = fixtures.flatMap((f) => demoItems(f));
const product = (i: Item) => {
  if (i.candidate.kind !== "product") throw new Error("not a product");
  return i.candidate;
};
// The Ohio demo products carry no package codes; one invented package makes a US product.
const usDemo = items.find(
  (i) => i.candidate.kind === "product" && i.candidate.region === "US",
)!;
const usItem: Item = {
  ...usDemo,
  candidate: {
    ...product(usDemo),
    packages: [{ ndc_published: "99999-123-30", ndc11: "99999012330" }],
  },
};
const trItem = items.find(
  (i) => i.candidate.kind === "product" && i.candidate.region === "TR",
)!;
const byName = items.find((i) => i.candidate.kind === "ingredient")!;
const withCountry = (
  country: "FR" | "ES",
  names: { product_name: string | null; brand_name: string | null },
): Candidate => ({
  ...product(trItem),
  region: "EU",
  country,
  ...names,
});

describe("W1: the request", () => {
  it("holds only the language, ingredient codes and the product's code or published name", () => {
    check(
      fc.property(
        fc.constantFrom(...items),
        fc.constantFrom(...LOCALES),
        fc.boolean(),
        fc.constantFrom("ZZSECRET box", "ZZSECRET"),
        (item, language, demo, secret) => {
          const marked: Item = {
            ...item,
            id: `${secret}-id`,
            boxName: secret,
            started: "2024-05",
            lot: "ZZSECRET1",
          };
          const q = infoQuery(en, marked, language, demo);
          const body = q.body!;
          expect(JSON.stringify(body)).not.toContain("ZZSECRET");
          expect(Object.keys(body).sort()).toEqual(
            body.product
              ? ["ingredients", "language", "product"]
              : ["ingredients", "language"],
          );
          expect(body.language).toBe(language);
          for (const i of body.ingredients) {
            expect(Object.keys(i)).toEqual(["atc_codes"]);
            for (const c of i.atc_codes)
              expect(c).toMatch(/^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$/);
            expect([...new Set(i.atc_codes)].sort()).toEqual(i.atc_codes);
          }
          // One entry per ingredient that could be checked, in the order shown.
          const askedShown = q.shown.filter((g) => g.key && !g.notChecked);
          expect(body.ingredients).toHaveLength(askedShown.length);
          expect(q.asked.filter((x) => x !== null)).toEqual(
            askedShown.map((_, n) => n),
          );
          if (demo) expect(body.product).toBeUndefined();
          if (body.product)
            expect(Object.keys(body.product).sort()).toEqual(
              body.product.country === "US"
                ? ["country", "ndc"]
                : ["country", "name"],
            );
        },
      ),
    );
  });

  it("asks a US product by its one product code", () => {
    const c = product(usItem);
    expect(productOf(c, false)).toEqual({
      product: { country: "US", ndc: "99999-0123" },
      reason: null,
    });
    const two: Candidate = {
      ...c,
      packages: [
        ...c.packages,
        { ndc_published: "99999-555-01", ndc11: "99999055501" },
      ],
    };
    expect(productOf(two, false)).toEqual({ product: null, reason: "no_code" });
    expect(productOf({ ...c, packages: [] }, false).reason).toBe("no_code");
  });

  it("asks a French product by its name and a Spanish one by its brand name", () => {
    const names = {
      product_name: "PRESENTACION (inventado)",
      brand_name: "MARCA (inventado)",
    };
    expect(productOf(withCountry("FR", names), false).product).toEqual({
      country: "FR",
      name: "PRESENTACION (inventado)",
    });
    expect(productOf(withCountry("ES", names), false).product).toEqual({
      country: "ES",
      name: "MARCA (inventado)",
    });
    expect(
      productOf(withCountry("ES", { ...names, brand_name: null }), false)
        .reason,
    ).toBe("no_code");
    expect(
      productOf(
        withCountry("FR", { ...names, product_name: "x".repeat(301) }),
        false,
      ).reason,
    ).toBe("no_code");
  });

  it("asks nothing official for other countries, names, demo and homeopathic products", () => {
    expect(productOf(product(trItem), false).reason).toBe("country");
    expect(productOf(byName.candidate, false).reason).toBe("by_name");
    expect(productOf(product(usItem), true)).toEqual({
      product: null,
      reason: "demo",
    });
    expect(
      productOf({ ...product(usItem), homeopathic: true }, false).reason,
    ).toBe("homeopathic");
  });

  it("does not ask about an ingredient that could not be checked", () => {
    const c = product(trItem);
    const unmapped: Candidate = {
      ...c,
      ingredients: c.ingredients.map((g) => ({
        ...g,
        status: "unmapped" as const,
        reason: "no_ingredient_key" as const,
        ingredient_key: null,
      })),
    };
    const q = infoQuery(en, { candidate: unmapped, choices: [] }, "en", false);
    expect(q.body).toBeNull();
    expect(q.asked.every((x) => x === null)).toBe(true);
    const homeopathic = infoQuery(
      en,
      { candidate: { ...product(usItem), homeopathic: true }, choices: [] },
      "en",
      false,
    );
    expect(homeopathic.body).toBeNull();
    expect(homeopathic.noProduct).toBe("homeopathic");
  });

  it("drops anything that is not an ingredient-level code and keeps the key stable", () => {
    const shown = infoQuery(en, trItem, "en", false).shown[0]!;
    expect(
      codesOf({
        ...shown,
        codes: ["C10AA05", "C10", "c10aa05", "A02BC01", "C10AA05"],
      }),
    ).toEqual(["A02BC01", "C10AA05"]);
    const a = infoQuery(en, trItem, "tr", false).body!;
    expect(queryKey(a)).toBe(
      queryKey(infoQuery(en, trItem, "tr", false).body!),
    );
    expect(queryKey(a)).not.toBe(
      queryKey(infoQuery(en, trItem, "de", false).body!),
    );
  });
});

describe("W2: the contract", () => {
  it("accepts the API's answers", () => {
    for (const [name, value] of Object.entries(answers)) {
      const r = decode(medicineInfoOut, value);
      expect(r.ok, name).toBe(true);
    }
    const us = decode(medicineInfoOut, answers.us);
    if (!us.ok) throw new Error(us.path);
    expect(us.value.official?.kind).toBe("label_text");
    expect(us.value.ingredients[0]!.abrupt_stop).toBe(true);
  });

  it("refuses a changed answer", () => {
    const us = answers.us as MedicineInfoOut & {
      official: Record<string, unknown>;
    };
    const fr = answers.fr as MedicineInfoOut & {
      official: Record<string, unknown>;
    };
    const bad: unknown[] = [
      { ...us, language: "it" },
      { ...us, official_status: "translated" },
      { ...us, ingredients: [{ ...us.ingredients[0], status: "all" }] },
      { ...us, ingredients: [{ ...us.ingredients[0], abrupt_stop: null }] },
      {
        ...us,
        ingredients: [
          {
            ...us.ingredients[0],
            groups: [{ ...us.ingredients[0]!.groups[0], text: " " }],
          },
        ],
      },
      {
        ...us,
        ingredients: [
          {
            ...us.ingredients[0],
            groups: [{ ...us.ingredients[0]!.groups[0], review_status: "ok" }],
          },
        ],
      },
      { ...us, official: { ...us.official, language: "tr" } },
      { ...us, official: { ...us.official, paragraphs: [] } },
      { ...us, official: { ...us.official, url: "https://example.org/x" } },
      { ...us, official: { ...us.official, kind: "translation" } },
      { ...fr, official: { ...fr.official, url: "https://example.org/x" } },
      { ...fr, official: { ...fr.official, language: "en" } },
    ];
    for (const value of bad)
      expect(decode(medicineInfoOut, value).ok).toBe(false);
  });

  it("maps errors to catalogue keys", () => {
    expect(
      messageKeyFor("medicine-info", 503, "medicine_info_unavailable"),
    ).toBe("PlainInfo.errors.unavailable");
    expect(messageKeyFor("medicine-info", 422, "invalid_request")).toBe(
      "Errors.client_defect",
    );
    expect(messageKeyFor("medicine-info", 500, null)).toBe("Errors.generic");
  });
});

describe("demo mode answers from a recorded-shaped file", () => {
  const codeSets = LOCALES.flatMap((language) =>
    items.flatMap((item) =>
      infoQuery(vocab(language), item, language, true).body!.ingredients.map(
        (i) => i.atc_codes.join(" "),
      ),
    ),
  );
  const recorded = plainInfoRecorded(codeSets);
  const demoInfo = recordedCall(async () => recorded);

  it("has an answer for every demo medicine in every language, without a product", async () => {
    for (const language of LOCALES)
      for (const item of items) {
        const q = infoQuery(vocab(language), item, language, true);
        const r = await demoInfo(q.body!);
        expect(r.ok, `${item.id} ${language}`).toBe(true);
        if (!r.ok) continue;
        expect(r.data.ingredients).toHaveLength(q.body!.ingredients.length);
        expect(r.data.official).toBeNull();
        expect(r.data.language).toBe(language);
      }
  });

  it("refuses a product and a code set that was not recorded", async () => {
    const call = recordedCall(async () => recorded);
    const body = infoQuery(en, usItem, "en", false).body!;
    expect((await call(body)).ok).toBe(false);
    const unknown = await call({
      language: "en",
      ingredients: [{ atc_codes: ["Z99ZZ99"] }],
    });
    expect(unknown).toEqual({
      ok: false,
      error: {
        kind: "contract",
        route: "medicine-info",
        messageKey: "Errors.generic",
      },
    });
    const failed = await recordedCall(async () => {
      throw new Error("chunk");
    })({ language: "en", ingredients: [] });
    expect(failed.ok).toBe(false);
  });
});

function flatten(tree: Tree, prefix = ""): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out.set(path, value);
    else for (const [k, v] of flatten(value, path)) out.set(k, v);
  }
  return out;
}
const texts = (l: Locale) =>
  new Map(
    [...flatten(catalogues[l])].filter(([k]) => k.startsWith("PlainInfo.")),
  );
const args = (message: string) =>
  [...message.matchAll(/\{\s*([A-Za-z_]\w*)\s*(?:\}|,)/g)]
    .map((m) => m[1]!)
    .sort();
describe.each(LOCALES)("W3: PlainInfo texts, %s", (l) => {
  const messages = texts(l);
  const english = texts("en");
  const t = createTranslator({ locale: l, messages: catalogues[l] as never });

  it("has every key of English, with the same parameters", () => {
    expect([...messages.keys()].sort()).toEqual([...english.keys()].sort());
    expect(messages.size).toBeGreaterThanOrEqual(50);
    for (const [key, value] of messages)
      expect(args(value), key).toEqual(args(english.get(key)!));
  });

  it("has no forbidden, reassurance or 'AI' word in any text or rendering", () => {
    for (const [key, value] of messages)
      expect(violations(value, l), key).toEqual([]);
    check(
      fc.property(
        fc.constantFrom(...messages.keys()),
        fc.constantFrom("amlodipine", "ZZ-12", "3 Nov 2026"),
        (key, word) => {
          const values = Object.fromEntries(
            args(messages.get(key)!).map((name) => [name, word]),
          );
          const out = t(key as never, values as never) as string;
          expect(violations(out, l), `${key}: ${out}`).toEqual([]);
        },
      ),
    );
  });

  it("marks the group sentences with the repository's review sentence", () => {
    expect(messages.get("PlainInfo.review")).toBe(
      flatten(catalogues[l]).get("TimeMachine.review"),
    );
    expect(violations(messages.get("PlainInfo.method")!, l)).toEqual([]);
  });
});

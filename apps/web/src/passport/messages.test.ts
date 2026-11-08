// Feature: medication-passport, Properties P4 and P16, and the message part of P3 (tasks 10.1,
// 10.2). Validates Req 1.3, 2.2, 6.1, 7.2, 8.1–8.3, 10.2: every Passport string in five locales,
// rendered with generated parameters, has no substitution, forbidden or reassurance word; the
// duplicate texts no removal word; every API code has a key in every locale; a presence answer
// carries codes, dates and the disclaimer only.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { createTranslator } from "next-intl";
import { describe, expect, it } from "vitest";

import { decode } from "@/api/decode";
import { routing } from "@/i18n/routing";
import { check, fc } from "@/test/fc";

import * as M from "./model";
import { findPrefixWords, passportWordViolations, type Locale } from "./words";

type Tree = { [key: string]: string | Tree };
const load = (locale: string): Tree =>
  JSON.parse(
    readFileSync(
      join(import.meta.dirname, "../../messages", `${locale}.json`),
      "utf8",
    ),
  ) as Tree;
function flatten(tree: Tree, prefix = ""): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out.set(path, value);
    else for (const [k, v] of flatten(value, path)) out.set(k, v);
  }
  return out;
}
const lit = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "fixtures", "schema-literals.json"),
    "utf8",
  ),
) as Record<string, string[] | string>;

const catalogues = Object.fromEntries(routing.locales.map((l) => [l, load(l)]));
const passport = (l: string) =>
  new Map(
    [...flatten(catalogues[l]!)].filter(([k]) => k.startsWith("Passport.")),
  );
const en = passport("en");

/** Argument names of an ICU message, with their kind (plural arguments are numbers). */
function args(message: string): Map<string, "number" | "text"> {
  const out = new Map<string, "number" | "text">();
  for (const m of message.matchAll(
    /\{\s*([A-Za-z_]\w*)\s*(?:\}|,\s*(plural|select))/g,
  ))
    if (!out.has(m[1]!) || m[2])
      out.set(m[1]!, m[2] === "plural" ? "number" : "text");
  return out;
}
const NUMERIC = new Set([
  "count",
  "equal",
  "comparable",
  "products",
  "ingredients",
]);
const textValue = fc.constantFrom(
  "TİTCK",
  "BDPM",
  "openFDA NDC",
  "2026-11-03",
  "ZZ-Name 5",
  "ZZ-Name 5, ZZ-Name 6",
  "40 mg",
);

const SAME: Record<Locale, string[]> = {
  en: ["same"],
  tr: ["aynı"],
  de: ["gleich", "dieselbe", "denselben", "derselben", "dasselbe"],
  fr: ["même"],
  es: ["mismo", "misma"],
};
const FRAMING: Record<Locale, string> = {
  en: "This may be worth mentioning to your doctor or pharmacist.",
  tr: "Bunu doktorunuza veya eczacınıza söylemek faydalı olabilir.",
  de: "Es kann sinnvoll sein, das Ihrer Ärztin, Ihrem Arzt oder Ihrer Apotheke zu sagen.",
  fr: "Il peut être utile d'en parler à votre médecin ou à votre pharmacien.",
  es: "Puede ser útil comentarlo con su médico o su farmacéutico.",
};

describe.each(routing.locales)("Passport namespace, %s", (locale) => {
  const l = locale as Locale;
  const messages = passport(locale);
  const t = createTranslator({
    locale,
    messages: catalogues[locale]! as never,
  });

  it("P4: no substitution, forbidden, reassurance or (duplicates) removal word", () => {
    expect(messages.size).toBeGreaterThan(100);
    for (const [key, value] of messages)
      expect(passportWordViolations(key, value, l), key).toEqual([]);
  });

  it("P4: rendered with generated parameters, every branch stays clean", () => {
    const keys = [...messages.keys()];
    check(
      fc.property(
        fc.constantFrom(...keys),
        fc.integer({ min: 0, max: 25 }),
        textValue,
        (key, n, text) => {
          const values: Record<string, string | number> = {};
          for (const [name, kind] of args(messages.get(key)!))
            values[name] = kind === "number" || NUMERIC.has(name) ? n : text;
          const out = t(key as never, values as never) as string;
          expect(passportWordViolations(key, out, l), `${key}: ${out}`).toEqual(
            [],
          );
        },
      ),
      { numRuns: 400 },
    );
  });

  it("duplicate flag ends with the allowed framing and keeps every box", () => {
    const text = messages.get("Passport.duplicate.text")!;
    for (const n of [2, 3]) {
      const out = t(
        "Passport.duplicate.text" as never,
        {
          ingredient: "ZZ",
          boxes: "A, B",
          count: n,
        } as never,
      ) as string;
      expect(out.endsWith(FRAMING[l]), out).toBe(true);
    }
    expect(text).toContain("{ingredient}");
    expect(text).toContain("{boxes}");
  });

  it("P3 (messages): 'could not compare' never says 'same'", () => {
    for (const [key, value] of messages)
      if (
        key.endsWith(".could_not_compare") ||
        key.startsWith("Passport.compareReason.")
      )
        expect(findPrefixWords(value, SAME[l]), key).toEqual([]);
  });

  it("P16: every API code and origin has a key, with the parameters of English", () => {
    const need = [
      ...(lit.status as string[]).map((s) => `status.${s}`),
      ...(lit.unavailable_reason as string[]).map((r) => `reason.${r}`),
      ...["strength", "dose_form", "strength_and_dose_form"].flatMap((f) =>
        (lit.result as string[]).map((r) => `compare.${f}.${r}`),
      ),
      ...["strength", "dose_form", "strength_and_dose_form"].map(
        (f) => `compareLabel.${f}`,
      ),
      ...(lit.cmp_reason as string[]).map((r) => `compareReason.${r}`),
      ...(lit.attribution as string[]).flatMap((a) => [
        `attribution.${a}`,
        `sourceName.${a}`,
      ]),
      ...(lit.notice as string[]).map((n) => `notice.${n}`),
      ...(lit.form_group as string[]).map((g) => `form.${g}`),
      ...["TR", "FR", "ES", "DE", "US", "EU", "OTHER"].map(
        (o) => `origin.${o}`,
      ),
      ...["TR", "FR", "ES", "DE", "US"].map((c) => `country.${c}`),
      ...(lit.basis as string[]).map((b) => `basis.${b}`),
      ...["mg", "g", "ug", "IU"].map((u) => `unit.${u}`),
      "listingsOnly",
      "entered",
      ...["loading", "loaded", "empty", "error", "partial", "recorded"].map(
        (s) => `states.${s}`,
      ),
    ].map((k) => `Passport.${k}`);
    for (const key of need) {
      expect(messages.get(key), key).toBeTruthy();
      expect([...args(messages.get(key)!).keys()].sort(), key).toEqual(
        [...args(en.get(key)!).keys()].sort(),
      );
    }
  });

  it("names the sources as published and keeps the attribution sentences", () => {
    for (const a of ["titck", "bdpm", "cima", "openfda"])
      expect(messages.get(`Passport.sourceName.${a}`)).toBe(
        en.get(`Passport.sourceName.${a}`),
      );
    expect(messages.get("Passport.attribution.bdpm")).toContain(
      "Base de données publique des médicaments (BDPM)",
    );
    expect(messages.get("Passport.attribution.cima")).toContain(
      "AEMPS, Nomenclátor de prescripción",
    );
    expect(messages.get("Passport.attribution.openfda")).toContain(
      "openFDA NDC directory",
    );
    expect(messages.get("Passport.attribution.titck")).toContain("TİTCK");
    for (const a of ["titck", "bdpm", "cima", "openfda"])
      expect(messages.get(`Passport.attribution.${a}`)).toContain("{date}");
  });

  it("follows the owner's word decisions (report word, no 'anonymous')", () => {
    const report = {
      en: "report",
      tr: "bildirim",
      de: "Meldung",
      fr: "signalement",
      es: "notificaci",
    };
    expect(
      findPrefixWords(messages.get("Passport.memory.entry")!, [report[l]]),
    ).toEqual([report[l]]);
    for (const [key, value] of messages)
      expect(
        findPrefixWords(value, ["anonym", "anonim", "anónim"]),
        key,
      ).toEqual([]);
  });
});

it("the English reference texts of design §7.2 are kept", () => {
  expect(en.get("Passport.listingsOnly")).toBe(
    "Janus shows listings in public data only. Only your doctor or pharmacist can say which medicine fits you.",
  );
  expect(en.get("Passport.homeopathic")).toBe(
    "Homeopathic product, not checked.",
  );
  expect(en.get("Passport.notice.presence_is_lower_bound")).toBe(
    "Products whose ingredients Janus could not recognise are not counted.",
  );
});

describe("word lists", () => {
  it("match at the start of a word only, in any case", () => {
    expect(findPrefixWords("A replacement box", ["replac"])).toEqual([
      "replac",
    ]);
    expect(findPrefixWords("Kutuyu çıkarın", ["çıkar"])).toEqual(["çıkar"]);
    expect(findPrefixWords("ÄQUIVALENT", ["äquivalent"])).toEqual([
      "äquivalent",
    ]);
    expect(findPrefixWords("unswitched", ["switch"])).toEqual([]);
    expect(passportWordViolations("Passport.x", "Remove one", "en")).toEqual(
      [],
    );
    expect(
      passportWordViolations("Passport.duplicate.x", "Remove one", "en"),
    ).toEqual(["remove"]);
  });
});

// --- API body walk (P4, last clause) --------------------------------------------------------
const cmpArb = fc.record({
  result: fc.constantFrom(...M.RESULTS),
  reason: fc.option(fc.constantFrom(...M.CMP_REASONS), { nil: null }),
  comparable: fc.nat(9),
  equal: fc.nat(9),
});
const keyArb = fc.integer({ min: 1, max: 999 }).map((n) => `Q${n}`);
const answerArb = fc.record({
  source: fc.nat(4),
  status: fc.constantFrom(...M.STATUSES),
  products: fc.nat(99),
  with_other_ingredients: fc.nat(99),
  keys_found: fc.array(keyArb, { maxLength: 3 }),
  homeopathic_left_out: fc.nat(9),
  comparison: fc.option(
    fc.record({
      strength: cmpArb,
      dose_form: cmpArb,
      strength_and_dose_form: cmpArb,
    }),
    { nil: null },
  ),
});
const sourceArb = fc.record({
  source: fc.nat(4),
  source_id: fc.option(fc.constantFrom(...M.SOURCE_IDS), { nil: null }),
  region: fc.constantFrom(...M.SOURCE_REGIONS),
  country: fc.option(fc.constantFrom(...M.SOURCE_COUNTRIES), { nil: null }),
  status: fc.constantFrom("loaded" as const, "source_unavailable" as const),
  reason: fc.option(fc.constantFrom(...M.UNAVAILABLE_REASONS), { nil: null }),
  snapshot_date: fc.option(fc.constantFrom("2026-11-06", "2026-11-03"), {
    nil: null,
  }),
  stale: fc.boolean(),
  attribution: fc.option(fc.constantFrom(...M.ATTRIBUTIONS), { nil: null }),
  as_published: fc.boolean(),
  can_compare: fc.record({ strength: fc.boolean(), dose_form: fc.boolean() }),
});
export const presenceOutArb = fc.record({
  dataset_version: fc.constant("a".repeat(64)),
  form_table_version: fc.constant("b".repeat(64)),
  sources: fc.array(sourceArb, { minLength: 5, maxLength: 5 }),
  items: fc.array(
    fc.record({
      item: fc.nat(49),
      keys: fc.array(keyArb, { minLength: 1, maxLength: 3 }),
      unknown_keys: fc.array(keyArb, { maxLength: 1 }),
      answers: fc.array(answerArb, { minLength: 5, maxLength: 5 }),
    }),
    { maxLength: 4 },
  ),
  notices: fc.subarray([...M.NOTICES]),
  disclaimer: fc.constant(lit.disclaimer as string),
});

const FIELD_NAMES = new Set([
  ...Object.keys(
    M.presenceOut.meta?.kind === "obj" ? M.presenceOut.meta.shape : {},
  ),
  ...Object.keys(
    M.sourceOut.meta?.kind === "obj" ? M.sourceOut.meta.shape : {},
  ),
  ...Object.keys(M.answer.meta?.kind === "obj" ? M.answer.meta.shape : {}),
  "item",
  "keys",
  "unknown_keys",
  "answers",
  "strength",
  "dose_form",
  "strength_and_dose_form",
  "result",
  "reason",
  "comparable",
  "equal",
]);
const CODES = new Set(
  Object.values(lit).flatMap((v) => (Array.isArray(v) ? v : [])),
);

/** Every string value and every key of a JSON value. */
function strings(v: unknown): string[] {
  if (typeof v === "string") return [v];
  if (Array.isArray(v)) return v.flatMap(strings);
  if (v && typeof v === "object")
    return Object.entries(v).flatMap(([k, x]) => [k, ...strings(x)]);
  return [];
}

export function onlyCodes(body: unknown): string[] {
  return strings(body).filter(
    (s) =>
      !(
        FIELD_NAMES.has(s) ||
        CODES.has(s) ||
        s === lit.disclaimer ||
        /^\d{4}-\d{2}-\d{2}$/.test(s) ||
        /^[0-9a-f]{64}$/.test(s) ||
        M.KEY.test(s)
      ),
  );
}

describe("P4: a presence answer carries codes, dates and the disclaimer only", () => {
  it("decodes and walks generated answers", () => {
    check(
      fc.property(presenceOutArb, (out) => {
        expect(decode(M.presenceOut, out).ok).toBe(true);
        expect(onlyCodes(out)).toEqual([]);
        expect(onlyCodes({ ...out, notices: ["Amlodipine 5 mg"] })).toEqual([
          "Amlodipine 5 mg",
        ]);
      }),
    );
  });
});

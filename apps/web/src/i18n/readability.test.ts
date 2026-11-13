// Plan D2.2: reading level of the patient texts, checked in CI. English uses the Flesch–Kincaid
// grade, Turkish Ateşman's score. Surface formulas are unstable on single short strings (they are
// meant for 100 words or more), so the target (school grade 6–8) applies to each patient message
// group and to the patient texts as a whole. A long text (20 words or more) on its own must stay
// under a ceiling one band looser (FK 10, Ateşman 40). Exempt: licence attributions and lists of
// source names (their wording is set by the publisher or is proper names), versioned consent
// texts (a wording change needs a new consent version) and the rows the doctor note shares word for
// word (apps/api/janus/notes/glossary/sentences.csv, column `shared`: a change goes through the
// glossary and the note together).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { parseCsv } from "../../scripts/gen-vocabulary.mjs";

import {
  meetsTarget,
  measuredTexts,
  PATIENT_NAMESPACES,
  plainText,
  type ReadingLocale,
  score,
  sentenceCount,
  syllablesEn,
  syllablesTr,
  words,
} from "./readability";

const LOCALES: ReadingLocale[] = ["en", "tr"];
const CEILING = { en: 10, tr: 40 } as const;
const MIN_GROUP = 5;
const EXEMPT = [
  /^Passport\.attribution\./,
  /^Privacy\.sources\.body$/,
  /^OutcomeConsent\./,
];

/** Message keys the doctor note shares word for word (sentences.csv, column `shared`). */
const SHARED = new Set(
  (
    parseCsv(
      readFileSync(
        join(
          import.meta.dirname,
          "../../../api/janus/notes/glossary/sentences.csv",
        ),
        "utf8",
      ),
    ) as Record<string, string>[]
  )
    .map((r) => r.shared)
    .filter((k): k is string => Boolean(k)),
);

const load = (l: ReadingLocale): Record<string, unknown> =>
  JSON.parse(
    readFileSync(join(import.meta.dirname, `../../messages/${l}.json`), "utf8"),
  ) as Record<string, unknown>;

describe("formula parts", () => {
  it("counts English syllables with the usual heuristic", () => {
    expect(syllablesEn("the")).toBe(1);
    expect(syllablesEn("medicine")).toBe(3);
    expect(syllablesEn("doctor")).toBe(2);
    expect(syllablesEn("cascade")).toBe(2);
  });
  it("counts one Turkish syllable per vowel", () => {
    expect(syllablesTr("ilaç")).toBe(2);
    expect(syllablesTr("doktorunuz")).toBe(4);
    expect(syllablesTr("İstanbul")).toBe(3);
  });
  it("keeps the other branch of a plural and shortens placeholders", () => {
    expect(
      plainText("{count, plural, one {# box} other {# boxes}} of {name}", "en"),
    ).toBe("2 boxes of it");
    expect(words(plainText("{n} ilaç", "tr"))).toEqual(["şu", "ilaç"]);
  });
  it("splits sentences at their ends", () => {
    expect(sentenceCount("One. Two! Three? Four")).toBe(4);
    expect(sentenceCount("A 2.5 mg dose")).toBe(1);
  });
  it("matches the published formulas on a worked example", () => {
    // 2 sentences, 11 words.
    const en = score(["The cat sat on the mat. The dog ran far away."], "en");
    expect(en.words).toBe(11);
    expect(en.sentences).toBe(2);
    expect(en.value).toBeCloseTo(
      0.39 * 5.5 + 11.8 * (en.syllables / 11) - 15.59,
    );
    const tr = score(["Kedi evde. Köpek bahçede koşuyor."], "tr");
    expect(tr.value).toBeCloseTo(
      198.825 - 40.175 * (tr.syllables / tr.words) - 2.61 * (tr.words / 2),
    );
  });
});

it("reads the doctor note's shared rows", () => {
  expect(SHARED.has("Memory.codes.disproportionate")).toBe(true);
  expect(SHARED.size).toBeGreaterThan(20);
});

describe.each(LOCALES)("patient texts, %s", (locale) => {
  const messages = load(locale);
  const groups = PATIENT_NAMESPACES.map((ns) => ({
    ns,
    texts: measuredTexts(messages, ns, locale),
  }));

  it("the patient texts as a whole meet the target", () => {
    const all = groups.flatMap((g) => g.texts.map((t) => t.text));
    expect(all.length).toBeGreaterThan(200);
    const s = score(all, locale);
    expect(meetsTarget(s.value, locale), `${s.value.toFixed(1)}`).toBe(true);
  });

  it("every patient group meets the target", () => {
    const failing = groups
      .filter((g) => g.texts.length >= MIN_GROUP)
      .map((g) => ({
        ns: g.ns,
        value: score(
          g.texts.map((t) => t.text),
          locale,
        ).value,
      }))
      .filter((g) => !meetsTarget(g.value, locale))
      .map((g) => `${g.ns}: ${g.value.toFixed(1)}`);
    expect(failing).toEqual([]);
  });

  it("no long text is above the ceiling", () => {
    const failing = groups
      .flatMap((g) => g.texts)
      .filter((t) => words(t.text).length >= 20)
      .filter((t) => !EXEMPT.some((re) => re.test(t.key)))
      .filter((t) => !SHARED.has(t.key))
      .map((t) => ({ key: t.key, value: score([t.text], locale).value }))
      .filter((t) =>
        locale === "en" ? t.value > CEILING.en : t.value < CEILING.tr,
      )
      .map((t) => `${t.key}: ${t.value.toFixed(1)}`);
    expect(failing).toEqual([]);
  });
});

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { findForbiddenPhrases, forbiddenPhrases } from "./forbidden-phrases";
import {
  allowedScreening,
  causalWords,
  memoryWordViolations,
  peopleWords,
  SCREENING_KEY,
  type Locale,
} from "./memory-words";
import { routing } from "./routing";

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
const memory = (locale: string) =>
  new Map([...flatten(load(locale))].filter(([k]) => k.startsWith("Memory.")));

// Every code the API can return (apps/api/janus/memory/messages.py, closed set).
const referenceCodes = [...memory(routing.defaultLocale).keys()]
  .filter((k) => k.startsWith("Memory.codes."))
  .map((k) => k.slice("Memory.codes.".length));

describe.each(routing.locales)("Memory namespace, %s", (locale) => {
  const messages = memory(locale);
  it("has every code of the closed set, with the same keys as English", () => {
    expect(referenceCodes.length).toBeGreaterThanOrEqual(35);
    expect([...messages.keys()].sort()).toEqual(
      [...memory(routing.defaultLocale).keys()].sort(),
    );
    for (const code of referenceCodes)
      expect(messages.get(`Memory.codes.${code}`), code).toBeTruthy();
  });
  it("names the counted thing as reports, never as people, and says nothing causal", () => {
    for (const [key, value] of messages) {
      expect(memoryWordViolations(key, value, locale as Locale), key).toEqual(
        [],
      );
    }
  });
  it("contains no forbidden medical phrase", () => {
    for (const [key, value] of messages) {
      expect(
        findForbiddenPhrases(value, forbiddenPhrases[locale]),
        key,
      ).toEqual([]);
    }
  });
  it("has the screening sentence exactly as allow-listed", () => {
    expect(messages.get(SCREENING_KEY)).toBe(allowedScreening[locale]);
    // the exception is real: without it the sentence would fail the causal-word list
    expect(
      findForbiddenPhrases(allowedScreening[locale], causalWords[locale])
        .length,
    ).toBeGreaterThan(0);
  });
  it("keeps the MedDRA trademark notice and the placeholders of templates", () => {
    expect(messages.get("Memory.meddra")).toBe(
      "MedDRA® trademark is registered by IFPMA on behalf of ICH.",
    );
    expect(messages.get("Memory.attribution")).toContain("{date}");
    expect(messages.get("Memory.codes.window_includes_follow_ups")).toMatch(
      /\{first\}.*\{last\}/,
    );
    expect(messages.get("Memory.codes.denominator_mapped_reports")).toContain(
      "{share}",
    );
  });
});

describe.each(routing.locales)("regional numbers, %s", (locale) => {
  const messages = memory(locale);
  const regions = ["US", "TR", "EU", "OTHER", "UNKNOWN"];
  const safety = [
    "crisis_support",
    "urgent_care_skin",
    "urgent_care_heart",
    "urgent_care_gi",
    "urgent_care_seizure",
    "urgent_care_breathing",
  ];
  it("has every region as a key, in both tables", () => {
    for (const region of regions) {
      expect(messages.get(`Memory.emergency.${region}`), region).toBeTruthy();
      expect(messages.get(`Memory.crisis.${region}`), region).toBeTruthy();
    }
  });
  it("keeps the numbers out of the sentences and uses the placeholders", () => {
    for (const code of safety) {
      const text = messages.get(`Memory.codes.${code}`) ?? "";
      expect(text, code).not.toMatch(/\d{3}/);
      expect(text, code).toContain(
        code === "crisis_support" ? "{crisis}" : "{emergency}",
      );
    }
  });
  it("gives 988 for the US, 112 for TR and EU, and no number for OTHER and UNKNOWN", () => {
    expect(messages.get("Memory.crisis.US")).toContain("988");
    expect(messages.get("Memory.emergency.US")).toContain("911");
    for (const region of ["TR", "EU"]) {
      expect(messages.get(`Memory.crisis.${region}`), region).toContain("112");
      expect(messages.get(`Memory.emergency.${region}`), region).toContain(
        "112",
      );
    }
    for (const region of ["OTHER", "UNKNOWN"]) {
      expect(messages.get(`Memory.crisis.${region}`), region).not.toMatch(/\d/);
      expect(messages.get(`Memory.emergency.${region}`), region).not.toMatch(
        /\d/,
      );
    }
    expect(messages.get("Memory.crisis.OTHER")).toBe(
      messages.get("Memory.crisis.UNKNOWN"),
    );
    expect(messages.get("Memory.emergency.OTHER")).toBe(
      messages.get("Memory.emergency.UNKNOWN"),
    );
  });
});

describe.each(routing.locales)("the single exception, %s", (locale) => {
  const l = locale as Locale;
  const sentence = allowedScreening[l];
  it("passes only as the complete value of Memory.screening", () => {
    expect(memoryWordViolations(SCREENING_KEY, sentence, l)).toEqual([]);
  });
  it("fails under any other key", () => {
    expect(
      memoryWordViolations("Memory.codes.weak", sentence, l).length,
    ).toBeGreaterThan(0);
  });
  it("fails when the sentence is changed in any way", () => {
    for (const changed of [
      sentence + " ",
      " " + sentence,
      sentence + "!",
      sentence.replace(/\s/, "  "),
      sentence.slice(0, -1),
      "Note. " + sentence,
      sentence + " " + sentence,
    ]) {
      expect(
        memoryWordViolations(SCREENING_KEY, changed, l).length,
        JSON.stringify(changed.slice(-12)),
      ).toBeGreaterThan(0);
    }
  });
  it("does not exempt people words even under the exception's key", () => {
    const people = peopleWords[l][0];
    expect(
      memoryWordViolations(SCREENING_KEY, `${sentence} ${people}`, l).length,
    ).toBeGreaterThan(0);
  });
});

describe("the word lists", () => {
  it("catch the obvious forms in English", () => {
    expect(
      memoryWordViolations("k", "Reports from people like you", "en").length,
    ).toBeGreaterThan(0);
    expect(
      memoryWordViolations("k", "This medicine is safe", "en").length,
    ).toBeGreaterThan(0);
    expect(memoryWordViolations("k", "2,300 reports", "en")).toEqual([]);
  });
});

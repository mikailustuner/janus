// Feature: experience, Property P12: every key in every locale, identical ICU placeholders,
// no forbidden phrase, no reassurance or compliance word, the `Memory` word lists over the
// Collective Memory screens, and Glass values without theme-device words (Req 2.1, 2.4, 6.5,
// 16.4, 21.5). The existing tests (same keys, no empty value, forbidden phrases) stay as they are.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { findForbiddenPhrases } from "./forbidden-phrases";
import { memoryWordViolations, type Locale } from "./memory-words";
import { complianceWords, reassurance, themeWords } from "./reassurance";
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

/** Argument names of an ICU message: `{name}` and `{name, plural, …}`, not nested text. */
export function placeholders(message: string): string[] {
  return [...message.matchAll(/\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*[,}]/g)]
    .map((m) => m[1]!)
    .sort();
}

const all = Object.fromEntries(
  routing.locales.map((l) => [l, flatten(load(l))]),
);
const reference = all[routing.defaultLocale]!;

describe.each(routing.locales)("catalogue %s", (locale) => {
  const messages = all[locale]!;
  const l = locale as Locale;

  it("has the placeholders of English in every message", () => {
    for (const [key, en] of reference) {
      expect(placeholders(messages.get(key) ?? ""), key).toEqual(
        placeholders(en),
      );
    }
  });

  it("has no reassurance word (rule 3) and no compliance claim", () => {
    for (const [key, value] of messages) {
      expect(findForbiddenPhrases(value, reassurance[l]), key).toEqual([]);
      expect(findForbiddenPhrases(value, complianceWords[l]), key).toEqual([]);
    }
  });

  it("keeps the Collective Memory screens to reports, without causal words", () => {
    for (const [key, value] of messages) {
      if (!key.startsWith("MemoryView.")) continue;
      expect(memoryWordViolations(key, value, l), key).toEqual([]);
    }
  });

  it("has no theme-device word in any Glass value", () => {
    const glass = [...messages].filter(([k]) => k.endsWith(".glass"));
    expect(glass.length).toBeGreaterThan(5);
    for (const [key, value] of glass) {
      expect(findForbiddenPhrases(value, themeWords[l]), key).toEqual([]);
    }
  });

  it("pairs every theme word key", () => {
    for (const key of messages.keys()) {
      if (key.endsWith(".twoFaces"))
        expect(messages.has(key.replace(/twoFaces$/, "glass")), key).toBe(true);
      if (key.endsWith(".glass"))
        expect(messages.has(key.replace(/glass$/, "twoFaces")), key).toBe(true);
    }
  });

  it("states rule 3 for the no-pattern result and keeps the disclaimer", () => {
    expect(messages.get("Findings.noPattern")).toBeTruthy();
    expect(messages.get("Disclaimer.text")).toBe(
      load(locale).Disclaimer && (load(locale).Disclaimer as Tree).text,
    );
  });
});

describe("placeholders()", () => {
  it("reads arguments and ignores plural branches", () => {
    expect(
      placeholders(
        "{count, plural, =0 {No ghost found} one {# ghost} other {# ghosts}} in {place}",
      ),
    ).toEqual(["count", "place"]);
  });
});

it("the English disclaimer is medical-safety rule 9 exactly", () => {
  expect(reference.get("Disclaimer.text")).toBe(
    "Janus provides information, not medical advice. Research prototype — not a medical device.",
  );
  expect(reference.get("Findings.noPattern")).toBe(
    "Janus found no pattern from its rule list. This does not mean your medicines are free of problems.",
  );
});

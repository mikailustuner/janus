import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { findForbiddenPhrases, forbiddenPhrases } from "./forbidden-phrases";
import { routing } from "./routing";

type Messages = { [key: string]: string | Messages };

const load = (locale: string): Messages =>
  JSON.parse(
    readFileSync(
      join(import.meta.dirname, "../../messages", `${locale}.json`),
      "utf8",
    ),
  ) as Messages;

function flatten(messages: Messages, prefix = ""): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(messages)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out.set(path, value);
    else for (const [k, v] of flatten(value, path)) out.set(k, v);
  }
  return out;
}

const reference = flatten(load(routing.defaultLocale));

describe.each(routing.locales)("messages/%s.json", (locale) => {
  const messages = flatten(load(locale));

  it("has exactly the same keys as the default locale", () => {
    const missing = [...reference.keys()].filter((k) => !messages.has(k));
    const extra = [...messages.keys()].filter((k) => !reference.has(k));
    expect({ missing, extra }, `messages/${locale}.json`).toEqual({
      missing: [],
      extra: [],
    });
  });

  it("has no empty strings", () => {
    for (const [key, value] of messages) {
      expect(value.trim(), key).not.toBe("");
    }
  });

  it("contains no forbidden phrases", () => {
    for (const [key, value] of messages) {
      expect(
        findForbiddenPhrases(value, forbiddenPhrases[locale]),
        key,
      ).toEqual([]);
    }
  });
});

describe("findForbiddenPhrases", () => {
  it("matches whole words only", () => {
    expect(findForbiddenPhrases("It cures nothing", ["cure"])).toEqual([]);
    expect(findForbiddenPhrases("A Cure!", ["cure"])).toEqual(["cure"]);
    expect(findForbiddenPhrases("tanıtım", ["tanı"])).toEqual([]);
    expect(findForbiddenPhrases("Kesin tanı", ["tanı"])).toEqual(["tanı"]);
  });
});

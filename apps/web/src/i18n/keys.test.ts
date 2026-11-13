// Every literal message key the code passes to the translator exists in the English catalogue
// (found 2026-11-13: ValidationStudies.modelkitPrecision.interval was used but missing, so the
// validation page showed the key path). Theme words (w("…")) need their two-faces variant.
// Keys built at run time (template literals) are not checked here.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");
const en = JSON.parse(
  readFileSync(join(import.meta.dirname, "../../messages/en.json"), "utf8"),
) as Record<string, unknown>;

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    const p = join(dir, d.name);
    if (d.isDirectory()) return files(p);
    return /\.tsx?$/.test(d.name) && !/\.test\.tsx?$/.test(d.name) ? [p] : [];
  });
}

function lookup(key: string): unknown {
  return key
    .split(".")
    .reduce<unknown>(
      (n, part) =>
        n && typeof n === "object"
          ? (n as Record<string, unknown>)[part]
          : undefined,
      en,
    );
}

it("every literal key used in the code is in the catalogue", () => {
  const call = /\b(t|w)\(\s*"([A-Z][A-Za-z]+(?:\.[A-Za-z0-9_-]+)+)"/g;
  const missing: string[] = [];
  let seen = 0;
  for (const file of files(SRC)) {
    const text = readFileSync(file, "utf8");
    for (const m of text.matchAll(call)) {
      seen++;
      const [, fn, key] = m;
      const value = fn === "w" ? lookup(`${key}.twoFaces`) : lookup(key!);
      if (typeof value !== "string")
        missing.push(`${file.slice(SRC.length + 1)}: ${key}`);
    }
  }
  expect(seen).toBeGreaterThan(1000);
  expect(missing).toEqual([]);
});

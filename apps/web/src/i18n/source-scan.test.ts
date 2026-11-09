/**
 * Medical-language guard: scans text under apps/ (web and api) for the forbidden phrases of
 * .kiro/steering/medical-safety.md, rule 2, in all five languages. Run by CI and by the
 * medical-language-guard hook. Suppress a justified line with the comment
 * "medical-language-guard: ignore".
 */
import { readdirSync, readFileSync } from "node:fs";
import { extname, join, relative } from "node:path";

import { expect, it } from "vitest";

import { findForbiddenPhrases, forbiddenPhrases } from "./forbidden-phrases";

const repoRoot = join(import.meta.dirname, "../../../..");
const SKIP_DIRS = new Set([
  "node_modules",
  ".next",
  ".venv",
  "__pycache__",
  ".pytest_cache",
  ".ruff_cache",
  ".hypothesis",
  "out",
  "build",
]);
const EXTENSIONS = new Set([
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".mjs",
  ".py",
  ".json",
  ".md",
  ".html",
]);
const EXCLUDE = [
  /(^|\/)forbidden-phrases\.ts$/, // the phrase list itself
  /(^|\/)janus\/notes\/phrases\.py$/, // its Python mirror (doctor-loop; a parity test keeps them equal)
  /\.test\.tsx?$/, // tests may quote phrases on purpose
  /(^|\/)test_[^/]*\.py$/,
  /(^|\/)(package|tsconfig)\.json$/,
  // Generated copy of data/report_channels.csv: official form labels quoted as published (e.g. FDA
  // 3500B "B2 Do you have a picture of the product?"). The labels the assistant shows are checked
  // by src/report/channels.test.ts (report-assistant).
  /(^|\/)src\/report\/channels\.json$/,
];
const PRAGMA = "medical-language-guard: ignore";

function* walk(dir: string): Generator<string> {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) yield* walk(join(dir, entry.name));
    } else if (EXTENSIONS.has(extname(entry.name))) {
      yield join(dir, entry.name);
    }
  }
}

it("no forbidden medical phrases in apps/ (medical-safety.md rule 2)", () => {
  const findings: string[] = [];
  for (const file of walk(join(repoRoot, "apps"))) {
    const rel = relative(repoRoot, file);
    if (EXCLUDE.some((re) => re.test(rel))) continue;
    readFileSync(file, "utf8")
      .split("\n")
      .forEach((line, i) => {
        if (line.includes(PRAGMA)) return;
        for (const [lang, phrases] of Object.entries(forbiddenPhrases)) {
          for (const phrase of findForbiddenPhrases(line, phrases)) {
            findings.push(`${rel}:${i + 1} [${lang}] "${phrase}"`);
          }
        }
      });
  }
  expect(findings, findings.join("\n")).toEqual([]);
});

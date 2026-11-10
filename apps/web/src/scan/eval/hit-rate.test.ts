// Feature: ocr-first, Requirement 5: the ingredient hit rate on the recorded text of the synthetic
// label images, before and after, equals the committed results; "after" is never worse than
// "before". The images are rendered text, not photos of real boxes.
//
//   OCR_EVAL_WRITE=1 pnpm vitest --run src/scan/eval/hit-rate.test.ts     rewrite results.json
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { buildIndex } from "../ingredient-match";

import {
  after,
  before,
  summarise,
  type Outcome,
  type Recorded,
  type Summary,
} from "./measure";

const here = import.meta.dirname;
const read = (p: string) => JSON.parse(readFileSync(join(here, p), "utf8"));
const names = read("../../vocabulary/ingredient-names.json") as Record<
  string,
  string[]
>;
const recorded = read("ocr-text.json") as Recorded[];
const index = buildIndex(names);

type Table = Record<string, { before: Summary; after: Summary }>;

async function measure(): Promise<Table> {
  const rows: { c: Recorded; b: Outcome; a: Outcome }[] = [];
  for (const c of recorded)
    rows.push({ c, b: before(c, names), a: await after(c, index) });
  const table: Table = {};
  const put = (name: string, pick: (c: Recorded) => boolean) => {
    const part = rows.filter((r) => pick(r.c));
    if (part.length)
      table[name] = {
        before: summarise(part.map((r) => r.b)),
        after: summarise(part.map((r) => r.a)),
      };
  };
  const named = (c: Recorded) => c.expected.length > 0;
  put("all labels that name a held ingredient", named);
  put(
    "held languages (en, tr, de, fr, es), one ingredient",
    (c) => c.group === "held",
  );
  for (const lang of ["en", "tr", "de", "fr", "es"])
    put(`  label in ${lang}`, (c) => c.group === "held" && c.lang === lang);
  put(
    "other languages (it, pt, nl, pl, Latin), one ingredient",
    (c) => c.group === "other",
  );
  put(
    "combination labels (every ingredient found)",
    (c) => c.group === "combination",
  );
  put(
    "upright or slightly tilted (0°, 2°, −4°, 7°)",
    (c) => named(c) && Math.abs(c.rotation) < 45,
  );
  put(
    "on its side or upside down (90°, 270°, 180°)",
    (c) => named(c) && Math.abs(c.rotation) >= 45,
  );
  for (const size of [13, 18, 26])
    put(
      `ingredient text ${size} px (image at 2×)`,
      (c) => named(c) && c.size === size,
    );
  for (const style of [
    "plain",
    "inverse",
    "band",
    "grey",
    "blur",
    "perspective",
    "noise",
    "jpeg",
    "lowres",
  ])
    put(`look: ${style}`, (c) => named(c) && c.style === style);
  put(
    "no held ingredient on the label (a candidate here is wrong)",
    (c) => !named(c),
  );
  return table;
}

describe("label evaluation on synthetic images", () => {
  it("gives the committed numbers, and after is never worse than before", async () => {
    const table = await measure();
    if (process.env.OCR_EVAL_WRITE)
      writeFileSync(
        join(here, "results.json"),
        JSON.stringify(table, null, 1) + "\n",
      );
    expect(table).toEqual(read("results.json"));
    for (const [name, row] of Object.entries(table)) {
      expect(row.after.hit, name).toBeGreaterThanOrEqual(row.before.hit);
      expect(row.after.cases).toBe(row.before.cases);
    }
    const none =
      table["no held ingredient on the label (a candidate here is wrong)"]!;
    expect(none.after.withWrong).toBe(0);
    console.table(
      Object.fromEntries(
        Object.entries(table).map(([k, r]) => [
          k,
          {
            labels: r.after.cases,
            "hit before": r.before.hit,
            "hit after": r.after.hit,
            "after %": Math.round((1000 * r.after.hit) / r.after.cases) / 10,
            "first after": r.after.first,
            "wrong cand. before": r.before.withWrong,
            "wrong cand. after": r.after.withWrong,
          },
        ]),
      ),
    );
  });
});

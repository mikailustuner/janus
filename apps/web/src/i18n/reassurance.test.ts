// Task 4.3: `reassurance.ts` equals `REASSURANCE` of apps/api/janus/notes/phrases.py.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, it } from "vitest";

import { reassurance } from "./reassurance";

it("mirrors REASSURANCE of the API exactly", () => {
  const py = readFileSync(
    join(import.meta.dirname, "../../../api/janus/notes/phrases.py"),
    "utf8",
  );
  const block = /^REASSURANCE[^=]*=\s*\{([\s\S]*?)\n\}/m.exec(py)?.[1];
  expect(block).toBeTruthy();
  const parsed: Record<string, string[]> = {};
  for (const m of block!.matchAll(/"(en|tr|de|fr|es|pt)":\s*\(([\s\S]*?)\)/g)) {
    parsed[m[1]!] = [...m[2]!.matchAll(/"([^"]*)"/g)].map((x) => x[1]!);
  }
  expect(parsed).toEqual(reassurance);
});

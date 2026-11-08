// Components and pages use tokens only, never a raw colour (experience design §7).
import { readdirSync, readFileSync } from "node:fs";
import { extname, join, relative } from "node:path";

import { expect, it } from "vitest";

const root = join(import.meta.dirname, "..");

function* walk(dir: string): Generator<string> {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) yield* walk(p);
    else if (
      [".ts", ".tsx", ".css"].includes(extname(e.name)) &&
      !e.name.includes(".test.")
    )
      yield p;
  }
}

it("src/components and src/app hold no hex, rgb or hsl colour", () => {
  const found: string[] = [];
  for (const dir of ["components", "app"])
    for (const file of walk(join(root, dir))) {
      readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (
            /#[0-9a-fA-F]{3,8}\b(?![-\w])|\brgba?\(|\bhsla?\(/.test(
              line.replace(/&#\d+;/g, ""),
            )
          )
            found.push(`${relative(root, file)}:${i + 1}`);
        });
    }
  expect(found).toEqual([]);
});

// Task 3.3: every letter of the five catalogues has a glyph in each font embedded in the PDF
// (read through fontkit, the font engine of @react-pdf/renderer), and the web fonts exist (Req 6.6, 17.8).
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { routing } from "@/i18n/routing";

// fontkit is a dependency of @react-pdf/font; resolve it from there (pnpm keeps it out of the app).
const fromRenderer = createRequire(
  createRequire(import.meta.url).resolve("@react-pdf/renderer"),
);
const fromFont = createRequire(fromRenderer.resolve("@react-pdf/font"));
const fontkit = fromFont("fontkit") as {
  create(buffer: Buffer): { hasGlyphForCodePoint(cp: number): boolean };
};

const web = join(import.meta.dirname, "../..");
/** Each PDF font with the fallback chain the PDF registers for it (src/note/pdf-fonts.ts). */
const PDF_FONTS: [string, string[]][] = [
  [
    "AtkinsonHyperlegibleNext-Regular.ttf",
    ["IBMPlexMono-Regular.ttf", "NotoSans-Fallback.ttf"],
  ],
  [
    "AtkinsonHyperlegibleNext-Bold.ttf",
    ["IBMPlexMono-Regular.ttf", "NotoSans-Fallback.ttf"],
  ],
  [
    "Fraunces-SemiBold.ttf",
    [
      "AtkinsonHyperlegibleNext-Bold.ttf",
      "IBMPlexMono-Regular.ttf",
      "NotoSans-Fallback.ttf",
    ],
  ],
  ["IBMPlexMono-Regular.ttf", ["NotoSans-Fallback.ttf"]],
];
const open = (file: string) =>
  fontkit.create(readFileSync(join(web, "public/fonts", file)));

function letters(): Set<string> {
  const out = new Set<string>();
  for (const locale of routing.locales) {
    const text = readFileSync(join(web, "messages", `${locale}.json`), "utf8");
    for (const ch of text) if (/\p{L}/u.test(ch)) out.add(ch);
  }
  for (const locale of routing.locales) {
    const v = readFileSync(
      join(web, "src/vocabulary", `${locale}.json`),
      "utf8",
    );
    for (const ch of v) if (/\p{L}/u.test(ch)) out.add(ch);
  }
  return out;
}

describe.each(PDF_FONTS)("%s", (file, fallbacks) => {
  // Counterexample found 2026-11-08: γ and Δ (γ-aminobutyric acid, Δ-9-tetrahydrocannabinol in the
  // reviewed fr/es/de names) are missing from the text fonts; the PDF falls back to Noto Sans.
  const chain = [open(file), ...fallbacks.map(open)];
  it("covers every letter of the catalogues and the vocabulary with its fallback chain", () => {
    const missing = [...letters()].filter(
      (ch) => !chain.some((f) => f.hasGlyphForCodePoint(ch.codePointAt(0)!)),
    );
    expect(missing.join("")).toBe("");
  });
  it("covers the Latin letters of the five languages by itself", () => {
    const latin = [...letters()].filter((ch) => /\p{Script=Latin}/u.test(ch));
    expect(
      latin
        .filter((ch) => !chain[0]!.hasGlyphForCodePoint(ch.codePointAt(0)!))
        .join(""),
    ).toBe("");
  });
});

it("the PDF can fall back to IBM Plex Mono for the arrow of the cascade sentence", () => {
  expect(
    open("IBMPlexMono-Regular.ttf").hasGlyphForCodePoint("→".codePointAt(0)!),
  ).toBe(true);
});

it("ships the web fonts and their licences", () => {
  for (const f of [
    "Fraunces-SemiBold.woff2",
    "AtkinsonHyperlegibleNext-Regular.woff2",
    "AtkinsonHyperlegibleNext-Bold.woff2",
    "IBMPlexMono-Regular.woff2",
    "Figtree-Variable.woff2",
    "OFL-Fraunces.txt",
    "OFL-AtkinsonHyperlegibleNext.txt",
    "OFL-IBMPlexMono.txt",
    "OFL-Figtree.txt",
  ])
    expect(existsSync(join(web, "src/fonts", f)), f).toBe(true);
});

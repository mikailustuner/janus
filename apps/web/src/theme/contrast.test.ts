// Feature: experience, Properties P18 and P40: every token pair marked as text or boundary in
// tokens.css passes WCAG contrast (text >= 4.5:1, boundary >= 3:1) in both themes (Night Pharmacy
// dark, Glass Janus light only since DP66), with reduced transparency on and off, and on the note
// paper (DP48); translucent tokens are composited over the ground (Req 3.1, 31.3). Example-based
// and exhaustive over the marked pairs.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(join(import.meta.dirname, "tokens.css"), "utf8");

type Rule = {
  conditions: string[];
  selector: string;
  decls: Record<string, string>;
};

/** A tiny parser for the token file: top-level rules and rules nested in @media / @supports. */
function parseRules(source: string): Rule[] {
  const text = source.replace(/\/\*[\s\S]*?\*\//g, "");
  const rules: Rule[] = [];
  const stack: string[] = [];
  let i = 0;
  let buf = "";
  while (i < text.length) {
    const c = text[i]!;
    if (c === "{") {
      const head = buf.trim();
      buf = "";
      if (head.startsWith("@")) {
        stack.push(head);
      } else {
        const end = text.indexOf("}", i);
        const body = text.slice(i + 1, end);
        const decls: Record<string, string> = {};
        for (const d of body.split(";")) {
          const m = /^\s*(--[a-z0-9-]+)\s*:\s*([\s\S]+?)\s*$/.exec(d);
          if (m) decls[m[1]!] = m[2]!;
        }
        rules.push({ conditions: [...stack], selector: head, decls });
        i = end;
      }
    } else if (c === "}") {
      stack.pop();
      buf = "";
    } else buf += c;
    i++;
  }
  return rules;
}

const rules = parseRules(css);

interface Context {
  name: string;
  theme: "two-faces" | "glass";
  paper?: boolean; // the note paper (`.paper`) inside the theme
  dark?: boolean;
  reduce?: boolean; // setting, media query or no backdrop-filter
}

function tokensFor(ctx: Context): Record<string, string> {
  const out: Record<string, string> = {};
  for (const r of rules) {
    const sel = r.selector;
    const matches = sel.split(",").some((s) => {
      const part = s.trim();
      if (part === ":root") return true;
      if (part.includes('data-theme-style="two-faces"'))
        return ctx.theme === "two-faces";
      if (part.includes('data-theme-style="glass"')) {
        if (ctx.theme !== "glass") return false;
        if (part.includes("data-reduce-transparency")) return !!ctx.reduce;
        return true;
      }
      return false;
    });
    if (!matches) continue;
    const condOk = r.conditions.every((cond) => {
      if (cond.includes("prefers-color-scheme: dark") && !ctx.dark)
        return false;
      if (cond.includes("prefers-reduced-transparency") && !ctx.reduce)
        return false;
      if (cond.startsWith("@supports not") && !ctx.reduce) return false;
      return true;
    });
    if (condOk) Object.assign(out, r.decls);
  }
  // The paper overrides the theme's tokens, whatever the theme (it is a class inside the page).
  if (ctx.paper)
    for (const r of rules)
      if (r.selector.trim() === ".paper") Object.assign(out, r.decls);
  return out;
}

type RGBA = [number, number, number, number];
function parseColor(v: string): RGBA {
  const hex = /^#([0-9a-f]{6})$/i.exec(v.trim());
  if (hex) {
    const n = parseInt(hex[1]!, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
  }
  const rgba =
    /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/.exec(
      v.trim(),
    );
  if (rgba)
    return [
      Number(rgba[1]),
      Number(rgba[2]),
      Number(rgba[3]),
      rgba[4] === undefined ? 1 : Number(rgba[4]),
    ];
  throw new Error(`not a colour: ${v}`);
}
const over = (top: RGBA, under: RGBA): RGBA => {
  const a = top[3];
  return [0, 1, 2]
    .map((i) => top[i]! * a + under[i]! * (1 - a))
    .concat(1) as RGBA;
};
function luminance([r, g, b]: RGBA): number {
  const f = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
export function contrast(a: RGBA, b: RGBA): number {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p) as [
    number,
    number,
  ];
  return (x + 0.05) / (y + 0.05);
}

const annotated = (tag: string) =>
  (new RegExp(`@${tag}([^\\n]*)`).exec(css)?.[1] ?? "")
    .trim()
    .split(/\s+/)
    .map((p) => p.split("/") as [string, string]);
const TEXT = annotated("contrast-text");
const BOUNDARY = annotated("contrast-boundary");

const contexts: Context[] = [
  { name: "Night Pharmacy", theme: "two-faces" },
  { name: "Note paper", theme: "two-faces", paper: true },
  { name: "Glass light", theme: "glass" },
  { name: "Glass light, reduce transparency", theme: "glass", reduce: true },
];

/** Every background a token can sit on in this context (one plain ground in both themes, DP67). */
function grounds(t: Record<string, string>): RGBA[] {
  return [parseColor(t["--bg"]!)];
}

describe.each(contexts)("$name", (ctx) => {
  const t = tokensFor(ctx);
  const resolve = (name: string): RGBA[] => {
    const ground = grounds(t);
    if (name === "bg") return ground;
    const surface = ground.map((g) => over(parseColor(t["--surface"]!), g));
    if (name === "surface") return surface;
    // Chips and buttons sit on cards; an rgba chip is composited over each card colour.
    const c = parseColor(t[`--${name}`]!);
    return c[3] < 1 ? surface.map((s) => over(c, s)) : [c];
  };

  it.each(TEXT.map(([f, b]) => ({ f, b })))(
    "text $f on $b >= 4.5:1",
    ({ f, b }) => {
      for (const fg of resolve(f))
        for (const bg of resolve(b))
          expect(contrast(fg, bg)).toBeGreaterThanOrEqual(4.5);
    },
  );

  it.each(BOUNDARY.map(([f, b]) => ({ f, b })))(
    "boundary $f on $b >= 3:1",
    ({ f, b }) => {
      for (const fg of resolve(f))
        for (const bg of resolve(b))
          expect(contrast(fg, bg)).toBeGreaterThanOrEqual(3);
    },
  );

  it("uses at least 72% opaque cards and the steering values", () => {
    const s = parseColor(t["--surface"]!);
    expect(s[3]).toBeGreaterThanOrEqual(0.72);
    if (ctx.theme === "glass") {
      // Clinical White (DP66, DP67): solid cards; navigation frosted unless transparency is reduced.
      expect(t["--surface"]).toBe("#ffffff");
      expect(parseColor(t["--nav-surface"]!)[3]).toBeGreaterThanOrEqual(0.86);
      if (ctx.reduce) {
        expect(t["--nav-surface"]).toBe("#ffffff");
        expect(t["--nav-blur"]).toBe("none");
      }
    }
  });
});

it("Glass Janus is light only: no colour-scheme rule in the token file (DP66)", () => {
  expect(
    rules.some((r) => r.conditions.some((c) => /prefers-color-scheme/.test(c))),
  ).toBe(false);
  expect(tokensFor({ name: "", theme: "glass", dark: true })).toEqual(
    tokensFor({ name: "", theme: "glass" }),
  );
});

it("annotates text and boundary pairs", () => {
  expect(TEXT.length).toBeGreaterThanOrEqual(12);
  expect(BOUNDARY.length).toBeGreaterThanOrEqual(2);
});

it("matches the steering tokens of design.md exactly", () => {
  const steering = readFileSync(
    join(import.meta.dirname, "../../../../.kiro/steering/design.md"),
    "utf8",
  );
  const night = tokensFor({ name: "", theme: "two-faces" });
  const paper = tokensFor({ name: "", theme: "two-faces", paper: true });
  for (const row of steering.matchAll(
    /^\| `(--[a-z-]+)`[^|]*\| `?(#[0-9A-F]{6})`?[^|]*\| `?(#[0-9A-F]{6})/gm,
  )) {
    expect(night[row[1]!]?.toLowerCase(), row[1]).toBe(row[2]!.toLowerCase());
    expect(paper[row[1]!]?.toLowerCase(), row[1]).toBe(row[3]!.toLowerCase());
  }
});

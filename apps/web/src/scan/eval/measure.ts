/**
 * The measurement of the label evaluation (ocr-first Req 5): for every recorded label, which
 * ingredients the device offers. "Before" is the reading the app made before this spec (one
 * pass, as photographed) with the plainest matcher (a printed word or phrase equals a held name
 * apart from letter case); "after" is the reading rule of `ocr-passes.ts` with
 * `matchIngredients`. Pure.
 */
import {
  matchIngredients,
  type IngredientCandidate,
  type NameIndex,
} from "../ingredient-match";
import { readLabel, type Pass, type Turns } from "../ocr-passes";

export interface EvalCase {
  id: string;
  group: "held" | "other" | "combination" | "none" | "not_held";
  lang: string;
  locale: "en" | "tr" | "de" | "fr" | "es";
  font: string;
  size: number;
  rotation: number;
  style: string;
  expected: string[];
}

interface Reading {
  confidence: number;
  lines: string[];
}

export interface Recorded extends EvalCase {
  /** One pass, as photographed, without the recogniser's own deskew (the app before). */
  before: Reading;
  /** By quarter turns; turned readings exist when the upright one was not confident. */
  passes: Partial<Record<Turns, Reading>>;
}

export interface Outcome {
  id: string;
  /** Every expected ingredient is among the candidates. */
  hit: boolean;
  /** The first candidate is an expected ingredient. */
  first: boolean;
  /** Candidates that are not an expected ingredient. */
  wrong: number;
}

/** The plainest matcher: a printed word or phrase equals a held name, ignoring letter case. */
export function plainMatch(
  lines: readonly string[],
  names: Readonly<Record<string, readonly string[]>>,
): string[] {
  // Two keys with one English name count as one ingredient, as in the matcher after.
  const first = new Map<string, string>();
  for (const [key, list] of Object.entries(names))
    if (!first.has(list[0]!)) first.set(list[0]!, key);
  const byName = new Map<string, string[]>();
  for (const list of Object.values(names))
    for (const n of list) {
      const k = n.toLowerCase();
      const key = first.get(list[0]!)!;
      if (!byName.get(k)?.includes(key))
        byName.set(k, [...(byName.get(k) ?? []), key]);
    }
  const out: string[] = [];
  for (const line of lines) {
    const w = line
      .toLowerCase()
      .split(/[^\p{L}\p{N}()]+/u)
      .filter(Boolean);
    for (let i = 0; i < w.length; i++)
      for (let n = 1; n <= 4 && i + n <= w.length; n++)
        for (const key of byName.get(w.slice(i, i + n).join(" ")) ?? [])
          if (!out.includes(key)) out.push(key);
  }
  return out;
}

const outcome = (c: EvalCase, keys: readonly string[]): Outcome => ({
  id: c.id,
  hit: c.expected.every((k) => keys.includes(k)),
  first: keys.length > 0 && c.expected.includes(keys[0]!),
  wrong: keys.filter((k) => !c.expected.includes(k)).length,
});

export function before(
  c: Recorded,
  names: Readonly<Record<string, readonly string[]>>,
): Outcome {
  return outcome(c, plainMatch(c.before.lines, names));
}

const pass = (r: Reading): Pass => ({
  confidence: r.confidence,
  lines: r.lines.map((text) => ({ text, words: text.split(/\s+/) })),
});

export async function candidatesAfter(
  c: Recorded,
  index: NameIndex,
): Promise<IngredientCandidate[]> {
  const match = (p: Pass) =>
    matchIngredients(
      p.lines.map((l) => l.text),
      index,
    );
  const chosen = await readLabel(
    async (turns) => {
      const r = c.passes[turns];
      if (!r) throw new Error(`${c.id}: no recorded reading for turn ${turns}`);
      return pass(r);
    },
    (p) => match(p).length > 0,
  );
  return match(chosen);
}

export async function after(c: Recorded, index: NameIndex): Promise<Outcome> {
  return outcome(
    c,
    (await candidatesAfter(c, index)).map((x) => x.key),
  );
}

export interface Summary {
  cases: number;
  hit: number;
  first: number;
  /** Labels with at least one candidate that is not an expected ingredient. */
  withWrong: number;
}

export function summarise(list: readonly Outcome[]): Summary {
  return {
    cases: list.length,
    hit: list.filter((o) => o.hit).length,
    first: list.filter((o) => o.first).length,
    withWrong: list.filter((o) => o.wrong > 0).length,
  };
}

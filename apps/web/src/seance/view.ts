/**
 * Pure view logic of the séance screen (séance design §7.3): the picker's choices, the three seats
 * in their fixed order, the locator text, and the cross-reference from a hypothesis card. It
 * computes no medical result (experience Req 23.3): the count and the missing witnesses are the
 * API's, shown as they come.
 */
import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "@/i18n/forbidden-phrases";

import {
  CONDITIONS,
  WITNESSES,
  type CatalogueOut,
  type Condition,
  type PairSummary,
  type PastItem,
  type SeanceIn,
  type SeanceOut,
  type Substance,
  type WitnessName,
} from "./model";

export interface Choice {
  substance: Substance;
  pairs: PairSummary[];
}

/**
 * One choice per substance that has at least one listed pair, in the catalogue's order; the
 * conditions of each in the fixed order wound, burn, ulcer, infection. `only` (demo mode) keeps
 * just those pairs.
 */
export function choices(
  cat: CatalogueOut,
  only: readonly SeanceIn[] | null = null,
): Choice[] {
  const keep = (p: PairSummary) =>
    !only ||
    only.some(
      (o) => o.substance === p.substance && o.condition === p.condition,
    );
  const out: Choice[] = [];
  for (const s of cat.substances) {
    const pairs = cat.pairs
      .filter((p) => p.substance === s.id && keep(p))
      .sort(
        (a, b) =>
          CONDITIONS.indexOf(a.condition) - CONDITIONS.indexOf(b.condition),
      );
    if (pairs.length) out.push({ substance: s, pairs });
  }
  return out;
}

/**
 * The headline pairs of séance design §4.5 and §7.3 rule 8 (passed both AI passes, no hazard,
 * two of three witnesses in the build of 2026-11-08): the screen opens on the first of them.
 */
export const FEATURED: readonly SeanceIn[] = [
  { substance: "st_johns_wort", condition: "wound" },
  { substance: "vinegar", condition: "infection" },
];

/** The pair to open first: the requested one, else a featured one, else the first listed. */
export function initialPair(
  list: readonly Choice[],
  wanted: SeanceIn | null,
): SeanceIn | null {
  const all = list.flatMap((c) => c.pairs);
  const listed = (w: SeanceIn) =>
    all.some((p) => p.substance === w.substance && p.condition === w.condition);
  const pick = [...(wanted ? [wanted] : []), ...FEATURED].find(listed);
  if (pick) return { substance: pick.substance, condition: pick.condition };
  const first = all[0];
  return first
    ? { substance: first.substance, condition: first.condition }
    : null;
}

/** The pair after choosing another substance: same condition when it has one, else its first. */
export function withSubstance(
  list: readonly Choice[],
  id: string,
  condition: Condition,
): SeanceIn | null {
  const c = list.find((x) => x.substance.id === id);
  if (!c) return null;
  const same = c.pairs.find((p) => p.condition === condition);
  return { substance: id, condition: (same ?? c.pairs[0]!).condition };
}

export type Seat =
  | { name: "past"; witness: SeanceOut["witnesses"]["past"] }
  | { name: "present"; witness: SeanceOut["witnesses"]["present"] }
  | { name: "science"; witness: SeanceOut["witnesses"]["science"] };

/** Always the three seats, in the order past, present, science (design §7.3 rule 1). */
export function seats(out: SeanceOut): Seat[] {
  return WITNESSES.map(
    (name) => ({ name, witness: out.witnesses[name] }) as Seat,
  );
}

/** The missing witnesses in seat order (the API's list, never recomputed). */
export function missingInOrder(out: SeanceOut): WitnessName[] {
  return WITNESSES.filter((w) => out.missing_witnesses.includes(w));
}

/** Message values of "Canon, Book 2, entry h0219, page V01P447, lines 12231–12232 (OpenITI)". */
export function locatorValues(item: PastItem): {
  book: number;
  entry: string;
  page: string;
  start: number;
  end: number;
} {
  const l = item.locator;
  return {
    book: l.book,
    entry: l.entry_id.split(".").pop() ?? l.entry_id,
    page: l.page ?? "",
    start: l.line_start,
    end: l.line_end,
  };
}

export interface CrossLink {
  substance: Substance;
  pairs: PairSummary[];
}

/**
 * Séance pairs reachable from a hypothesis card of the FAERS ingredient `key`: only substances
 * whose present link is the same exposure or a component of it. A `different` exposure (salt →
 * intravenous sodium chloride, DP11) is never offered as the same thing.
 */
export function crossLinks(cat: CatalogueOut, key: string): CrossLink[] {
  return choices(cat)
    .map((c) => ({
      substance: c.substance,
      pairs: c.pairs.filter(
        (p) =>
          p.present_ingredient_key === key &&
          (p.present_link === "same" || p.present_link === "component"),
      ),
    }))
    .filter((c) => c.pairs.length > 0);
}

/** A DOI as a resolver link (DOIs are case-insensitive; the path keeps its characters). */
export function doiUrl(doi: string): string {
  return `https://doi.org/${doi.split("/").map(encodeURIComponent).join("/")}`;
}

/**
 * A paper title is shown only when it holds no forbidden phrase of medical-safety rule 2 (titles
 * are English data; such a title is withheld and the DOI stays).
 */
export function showableTitle(title: string): boolean {
  return findForbiddenPhrases(title, forbiddenPhrases.en).length === 0;
}

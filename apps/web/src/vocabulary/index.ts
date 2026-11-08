/**
 * The generated clinical vocabulary (experience design §8.3, DP17) and its lookups. Pure: the
 * functions take the loaded vocabulary; `load()` fetches a locale's file as a lazy chunk.
 *
 * The ingredient name rule is doctor-loop DP16 / design §5.7 exactly: the accepted name of the
 * language (English with its alternative name), else the accepted English INN tagged "name not
 * translated", else the unreviewed English label tagged "name not reviewed", else the code only.
 */
import type { Locale } from "@/api/contracts";

export interface EventEntry {
  label: string;
  safety_line: SafetyLineCode | null;
  direction: string;
  pipc_positions: number[];
}

export type SafetyLineCode =
  | "crisis_support"
  | "urgent_care_skin"
  | "urgent_care_heart"
  | "urgent_care_gi"
  | "urgent_care_seizure"
  | "urgent_care_breathing";

export interface Vocabulary {
  events: Record<string, EventEntry>;
  cascades: Record<
    string,
    {
      drug_a: string;
      adverse_event: string;
      drug_b: string;
      translated: boolean;
    }
  >;
  ingredients: Record<string, string>;
  sentences: Record<string, string>;
}

export interface VocabularyIndex {
  sources: Record<string, string>;
  english_names: Record<string, string>;
}

export interface Loaded {
  locale: Locale;
  vocab: Vocabulary;
  index: VocabularyIndex;
}

export type NameBasis =
  "glossary" | "english_fallback" | "not_reviewed" | "code_only";

export interface IngredientName {
  text: string | null;
  basis: NameBasis;
  /** "name not translated" / "name not reviewed", in the locale; null for a glossary name. */
  tag: string | null;
}

export function ingredientName(
  v: Loaded,
  key: string,
  labelEn: string | null,
): IngredientName {
  const own = v.vocab.ingredients[key];
  if (own) return { text: own, basis: "glossary", tag: null };
  const en = v.index.english_names[key];
  if (en)
    return {
      text: en,
      basis: "english_fallback",
      tag: v.vocab.sentences["name.not_translated"]!,
    };
  if (labelEn)
    return {
      text: labelEn,
      basis: "not_reviewed",
      tag: v.vocab.sentences["name.not_reviewed"]!,
    };
  return {
    text: null,
    basis: "code_only",
    tag: v.vocab.sentences["name.not_reviewed"]!,
  };
}

/** Rule row of a PIPC rule id `pipc:<n>`. */
export function ruleRow(ruleId: string): number | null {
  const m = /^pipc:([0-9]+)$/.exec(ruleId);
  return m ? Number(m[1]) : null;
}

export function cascadeName(v: Loaded, ruleId: string) {
  const row = ruleRow(ruleId);
  return row === null ? null : (v.vocab.cascades[String(row)] ?? null);
}

export function eventEntry(v: Loaded, key: string): EventEntry | null {
  return v.vocab.events[key] ?? null;
}

/** The one Janus event key whose `pipc_positions` holds the rule's row, else null (Req 7.5). */
export function eventKeyForRule(v: Loaded, ruleId: string): string | null {
  const row = ruleRow(ruleId);
  if (row === null) return null;
  const keys = Object.entries(v.vocab.events)
    .filter(([, e]) => e.pipc_positions.includes(row))
    .map(([k]) => k);
  return keys.length === 1 ? keys[0]! : null;
}

export function sentence(v: Loaded, id: string): string {
  const s = v.vocab.sentences[id];
  if (s === undefined) throw new Error(`vocabulary sentence missing: ${id}`);
  return s;
}

const cache = new Map<Locale, Promise<Loaded>>();

const loaders: Record<Locale, () => Promise<{ default: unknown }>> = {
  en: () => import("./en.json"),
  tr: () => import("./tr.json"),
  de: () => import("./de.json"),
  fr: () => import("./fr.json"),
  es: () => import("./es.json"),
};

export function load(locale: Locale): Promise<Loaded> {
  let p = cache.get(locale);
  if (!p) {
    p = Promise.all([loaders[locale](), import("./index.json")]).then(
      ([v, i]) => ({
        locale,
        vocab: v.default as Vocabulary,
        index: i.default as VocabularyIndex,
      }),
    );
    p.catch(() => cache.delete(locale));
    cache.set(locale, p);
  }
  return p;
}

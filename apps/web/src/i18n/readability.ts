/**
 * Reading level of the patient texts (plan D2.2): Flesch–Kincaid grade for English, Ateşman's
 * readability score for Turkish (Ateşman E. Türkçede okunabilirliğin ölçülmesi. Dil Dergisi
 * 1997;58:71–74). Both are surface formulas over words per sentence and syllables per word; they
 * do not measure whether a text is understood, only how hard it is to read.
 *
 * Message strings are ICU templates: a plural or select keeps its `other` branch, a placeholder
 * counts as one short word. Only strings that read as sentences (six words or more) are measured;
 * labels and buttons are left out, since every one of them would count as a one-word sentence.
 */

/** The patient-facing message groups (the clinician note, research and evidence detail excluded). */
export const PATIENT_NAMESPACES = [
  "Home",
  "Disclaimer",
  "Emergency",
  "Errors",
  "Storage",
  "Start",
  "Scan",
  "Settings",
  "Medicines",
  "Timeline",
  "Findings",
  "MemoryView",
  "Note",
  "Withdraw",
  "Confirm",
  "OutcomeConsent",
  "Reminder",
  "Privacy",
  "Memory",
  "Passport",
  "ZombieAlert",
  "Recall",
  "SafetyCheck",
  "PlainInfo",
] as const;

export type ReadingLocale = "en" | "tr";

/** Targets (plan D2.2: school grade 6–8): FK grade at most 8; Ateşman 50 or more (grade 7–8). */
export const TARGET = { en: 8, tr: 50 } as const;

const PLACEHOLDER_WORD = { en: "it", tr: "şu" } as const;

/** Replaces ICU plural/select blocks by their `other` branch and placeholders by a short word. */
export function plainText(template: string, locale: ReadingLocale): string {
  let s = template;
  // Innermost-first: a `{x, plural|select|selectordinal, ...}` block becomes its `other` text.
  const block =
    /\{\s*\w+\s*,\s*(?:plural|select|selectordinal)\s*,((?:[^{}]|\{[^{}]*\})*)\}/;
  for (let guard = 0; guard < 20 && block.test(s); guard++) {
    s = s.replace(block, (_m, body: string) => {
      const other = /other\s*\{([^{}]*)\}/.exec(body);
      return other?.[1] ?? "";
    });
  }
  return s
    .replace(/#/g, "2")
    .replace(/\{[^{}]*\}/g, PLACEHOLDER_WORD[locale])
    .replace(/<\/?\w+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const WORD = /[\p{L}][\p{L}'’-]*/gu;

export function words(text: string): string[] {
  return text.match(WORD) ?? [];
}

/** Sentences: split at . ! ? … ; and at line ends; a string's end ends its last sentence. */
export function sentenceCount(text: string): number {
  const parts = text
    .split(/[.!?…;:]+(?=\s|$)|\n+/u)
    .filter((p) => words(p).length > 0);
  return Math.max(1, parts.length);
}

/** English syllables: vowel groups, less a silent final e, at least one. A standard heuristic. */
export function syllablesEn(word: string): number {
  const w = word.toLowerCase().replace(/[^a-z]/g, "");
  if (!w) return 1;
  if (w.length <= 3) return 1;
  const trimmed = w
    .replace(/(?:[^laeiouy]es|[^laeiouy]ed|[^laeiouy]e)$/, "")
    .replace(/^y/, "");
  const groups = trimmed.match(/[aeiouy]{1,2}/g);
  return Math.max(1, groups?.length ?? 1);
}

/** Turkish syllables: one per vowel (Turkish has no diphthongs). */
export function syllablesTr(word: string): number {
  const groups = word.toLocaleLowerCase("tr").match(/[aeıioöuüâîû]/g);
  return Math.max(1, groups?.length ?? 1);
}

export type Score = {
  words: number;
  sentences: number;
  syllables: number;
  /** FK grade (en) or Ateşman score (tr). */
  value: number;
};

export function score(texts: string[], locale: ReadingLocale): Score {
  let w = 0;
  let s = 0;
  let syl = 0;
  const count = locale === "en" ? syllablesEn : syllablesTr;
  for (const t of texts) {
    const ws = words(t);
    w += ws.length;
    s += sentenceCount(t);
    for (const x of ws) syl += count(x);
  }
  const wps = w / Math.max(1, s);
  const spw = syl / Math.max(1, w);
  const value =
    locale === "en"
      ? 0.39 * wps + 11.8 * spw - 15.59
      : 198.825 - 40.175 * spw - 2.61 * wps;
  return { words: w, sentences: s, syllables: syl, value };
}

/** True when the score meets the target (lower FK grade is easier; higher Ateşman is easier). */
export function meetsTarget(value: number, locale: ReadingLocale): boolean {
  return locale === "en" ? value <= TARGET.en : value >= TARGET.tr;
}

/** Every string under a message node, with its key path. */
export function strings(
  node: unknown,
  path = "",
): { key: string; text: string }[] {
  if (typeof node === "string") return [{ key: path, text: node }];
  if (node && typeof node === "object") {
    return Object.entries(node as Record<string, unknown>).flatMap(([k, v]) =>
      strings(v, path ? `${path}.${k}` : k),
    );
  }
  return [];
}

/** The measured sentences of one namespace: plain text of every string with six words or more. */
export function measuredTexts(
  messages: Record<string, unknown>,
  namespace: string,
  locale: ReadingLocale,
): { key: string; text: string }[] {
  return strings(messages[namespace], namespace)
    .map(({ key, text }) => ({ key, text: plainText(text, locale) }))
    .filter(({ text }) => words(text).length >= 6);
}

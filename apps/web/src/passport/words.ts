/**
 * Passport word lists (medication-passport design §7.3, Req 1.3, 8.1, 8.2, P4). Matching is a
 * whole-word prefix match, case-insensitive: an entry matches where a word starts with it
 * ("replac" matches "replacement", "çıkar" matches "çıkarın"), never inside a word.
 *
 * - `substitutionWords`: every `Passport.*` string. The Passport informs; it never suggests that
 *   one product can take another's place, in any language (DP3, DP15).
 * - `removalWords`: every `Passport.duplicate.*` string. A duplicate flag never suggests taking an
 *   item off the list or leaving one out (Req 1.3, DP14).
 * Plus, for every Passport string, the rule-2 forbidden phrases and the rule-3 reassurance words.
 */
import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "@/i18n/forbidden-phrases";
import { reassurance } from "@/i18n/reassurance";

export type Locale = "en" | "tr" | "de" | "fr" | "es" | "pt";

export const substitutionWords: Record<Locale, readonly string[]> = {
  en: [
    "equivalent",
    "interchangeab",
    "instead",
    "switch",
    "replac",
    "substitut",
    "alternative",
    "same as your",
    "you can use",
  ],
  tr: [
    "muadil",
    "eşdeğer",
    "yerine",
    "değiştir",
    "kullanabilirsiniz",
    "aynısı",
  ],
  de: [
    "gleichwertig",
    "äquivalent",
    "austauschbar",
    "stattdessen",
    "ersetz",
    "Ersatz",
    "wechseln",
    "umsteigen",
    "Alternative",
  ],
  fr: [
    "équivalent",
    "interchangeable",
    "à la place",
    "remplac",
    "substitu",
    "changer de",
    "alternative",
  ],
  es: [
    "equivalente",
    "intercambiable",
    "en lugar de",
    "en vez de",
    "sustitu",
    "reemplaz",
    "cambiar a",
    "alternativa",
  ],
  pt: [
    "equivalente",
    "intercambiável",
    "em vez de",
    "em lugar de",
    "substitu",
    "trocar por",
    "mudar para",
    "alternativa",
  ],
};

export const removalWords: Record<Locale, readonly string[]> = {
  en: [
    "remove",
    "delet",
    "take only one",
    "need both",
    "one of them is enough",
    "drop",
  ],
  tr: ["çıkar", "sil", "birini bırak", "ikisine gerek", "yalnızca birini"],
  de: ["entfern", "lösch", "nur eines", "brauchen Sie nicht"],
  fr: ["supprim", "retir", "un seul suffit", "besoin des deux"],
  es: ["elimin", "quit", "borr", "solo uno", "necesita ambos"],
  pt: [
    "remov",
    "elimin",
    "apag",
    "retir",
    "apenas um",
    "só um",
    "precisa de ambos",
    "um deles basta",
  ],
};

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** The entries of `words` that start a word of `text` (case-insensitive). */
export function findPrefixWords(
  text: string,
  words: readonly string[],
): string[] {
  return words.filter((w) =>
    new RegExp(`(?<!\\p{L})${escape(w)}`, "iu").test(text),
  );
}

/** Every word-list hit of one `Passport.*` message (empty when the text is clean). */
export function passportWordViolations(
  key: string,
  text: string,
  locale: Locale,
): string[] {
  return [
    ...findPrefixWords(text, substitutionWords[locale]),
    ...(key.startsWith("Passport.duplicate.")
      ? findPrefixWords(text, removalWords[locale])
      : []),
    ...findForbiddenPhrases(text, forbiddenPhrases[locale]),
    ...findForbiddenPhrases(text, reassurance[locale]),
  ];
}

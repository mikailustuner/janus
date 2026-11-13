/** Word rules of the medicine-information texts: forbidden, reassurance and "AI" words. */
import type { Locale } from "@/api/contracts";
import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "@/i18n/forbidden-phrases";
import { reassurance } from "@/i18n/reassurance";

const AI: Record<Locale, string[]> = {
  en: ["AI", "artificial intelligence"],
  tr: ["yapay zeka", "yapay zekâ"],
  de: ["KI", "künstliche Intelligenz"],
  fr: ["IA", "intelligence artificielle"],
  es: ["IA", "inteligencia artificial"],
  pt: ["IA", "inteligência artificial"],
};

export const violations = (value: string, l: Locale) => [
  ...findForbiddenPhrases(value, forbiddenPhrases[l]),
  ...findForbiddenPhrases(value, reassurance[l]),
  ...AI[l].filter((w) =>
    new RegExp(`(?<!\\p{L})${w}(?!\\p{L})`, "u").test(value),
  ),
];

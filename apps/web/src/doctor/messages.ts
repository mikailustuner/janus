/**
 * The doctor page's own small message map (design §11): the `Doctor` namespace and the
 * disclaimer of the five catalogues, generated into messages.json by scripts/gen-vocabulary.mjs
 * (a parity test keeps it equal to messages/*.json). The page has no other providers.
 */
import map from "./messages.json";

export type Lang = "en" | "tr" | "de" | "fr" | "es" | "pt";
export type DoctorMessages = (typeof map)["en"];

export const DOCTOR_MESSAGES = map as Record<Lang, DoctorMessages>;

export function browserLang(languages: readonly string[]): Lang {
  for (const l of languages) {
    const short = l.slice(0, 2).toLowerCase();
    if (short in DOCTOR_MESSAGES) return short as Lang;
  }
  return "en";
}

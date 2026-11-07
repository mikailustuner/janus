/**
 * Phrases that must never appear in user-facing text (.kiro/steering/medical-safety.md, rule 2).
 * Keep this list in sync with the steering file.
 */
export const forbiddenPhrases = {
  en: [
    "stop taking",
    "you should stop",
    "discontinue",
    "unnecessary medicine",
    "cure",
    "cures",
    "treatment for",
    "diagnosis",
    "you have",
    "safe to stop",
    "your medicines are safe",
  ],
  tr: [
    "ilacı bırakın",
    "ilacınızı kesin",
    "gereksiz ilaç",
    "tedavi eder",
    "tanı",
    "ilaçlarınız güvenli",
  ],
  de: [
    "absetzen Sie",
    "nicht mehr einnehmen",
    "unnötiges Medikament",
    "heilt",
    "Diagnose",
  ],
  fr: ["arrêtez de prendre", "médicament inutile", "guérit", "diagnostic"],
  es: ["deje de tomar", "medicamento innecesario", "cura", "diagnóstico"],
} as const;

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Returns the forbidden phrases found in `text`, matched as whole words, case-insensitive. */
export function findForbiddenPhrases(
  text: string,
  phrases: readonly string[],
): string[] {
  return phrases.filter((phrase) =>
    new RegExp(`(?<!\\p{L})${escape(phrase)}(?!\\p{L})`, "iu").test(text),
  );
}

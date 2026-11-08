/**
 * Word lists for the `Memory` message namespace (collective-memory design §7.2, Requirement 8).
 *
 * Counts in Collective Memory are reports, never people: the words for people are forbidden. No string
 * may say or imply causation, probability, risk to the reader, safety, normality or interaction.
 * Owner decision 2026-11-08: ONE exception, the screening sentence, which must be the complete value
 * of the message `Memory.screening` and equal to the allowed string of its language.
 *
 * Matching follows `findForbiddenPhrases`: whole words, case-insensitive.
 */
import { findForbiddenPhrases } from "./forbidden-phrases";

export const peopleWords = {
  en: [
    "people",
    "person",
    "persons",
    "patient",
    "patients",
    "individual",
    "individuals",
    "humans",
    "someone",
    "anyone",
    "like you",
  ],
  tr: [
    "kişi",
    "kişiler",
    "hasta",
    "hastalar",
    "insan",
    "insanlar",
    "sizin gibi",
  ],
  de: [
    "Menschen",
    "Mensch",
    "Personen",
    "Person",
    "Patienten",
    "Patient",
    "Leute",
    "wie Sie",
  ],
  fr: ["personne", "personnes", "patient", "patients", "gens", "comme vous"],
  es: [
    "persona",
    "personas",
    "paciente",
    "pacientes",
    "gente",
    "como usted",
    "como tú",
  ],
} as const;

export const causalWords = {
  en: [
    "cause",
    "causes",
    "caused",
    "causing",
    "because of",
    "due to",
    "risk",
    "risks",
    "chance",
    "chances",
    "probability",
    "likely",
    "unlikely",
    "safe",
    "unsafe",
    "dangerous",
    "harmless",
    "normal",
    "unusual",
    "interact",
    "interacts",
    "interaction",
    "interactions",
    "side effect",
    "side effects",
    "reaction",
    "reactions",
  ],
  tr: [
    "neden olur",
    "neden olan",
    "neden olduğuna",
    "nedeniyle",
    "risk",
    "riskler",
    "olasılık",
    "güvenli",
    "tehlikeli",
    "normal",
    "olağandışı",
    "etkileşim",
    "yan etki",
    "yan etkiler",
    "reaksiyon",
  ],
  de: [
    "verursacht",
    "verursachen",
    "verursachte",
    "Ursache",
    "Ursachen",
    "Risiko",
    "Risiken",
    "Wahrscheinlichkeit",
    "sicher",
    "gefährlich",
    "normal",
    "ungewöhnlich",
    "Wechselwirkung",
    "Wechselwirkungen",
    "Nebenwirkung",
    "Nebenwirkungen",
    "Reaktion",
    "Reaktionen",
  ],
  fr: [
    "cause",
    "causes",
    "provoque",
    "provoquent",
    "causent",
    "causer",
    "risque",
    "risques",
    "probabilité",
    "sûr",
    "sûre",
    "dangereux",
    "normal",
    "normale",
    "inhabituel",
    "interaction",
    "interactions",
    "effet secondaire",
    "effets secondaires",
    "réaction",
    "réactions",
  ],
  es: [
    "causa",
    "causas",
    "cause",
    "causen",
    "causar",
    "provoca",
    "provocan",
    "provoque",
    "provocar",
    "riesgo",
    "riesgos",
    "probabilidad",
    "seguro",
    "segura",
    "peligroso",
    "normal",
    "inusual",
    "interacción",
    "interacciones",
    "efecto secundario",
    "efectos secundarios",
    "reacción",
    "reacciones",
  ],
} as const;

/** The single allow-listed exception, per language (statistics review Q6; owner decision 2026-11-08). */
export const allowedScreening = {
  en: "This is a screening statistic. Many medicine–event pairs are examined at once and most of them meet these criteria, so meeting them is common and is not evidence that the medicine causes the event.",
  tr: "Bu bir tarama istatistiğidir. Çok sayıda ilaç–olay çifti aynı anda incelenir ve çoğu bu ölçütleri karşılar; bu yüzden ölçütleri karşılamak yaygındır ve ilacın olaya neden olduğuna dair bir kanıt değildir.",
  de: "Dies ist eine Screening-Statistik. Viele Kombinationen aus Arzneimittel und Ereignis werden gleichzeitig geprüft und die meisten erfüllen diese Kriterien. Diese Kriterien zu erfüllen ist daher häufig und kein Beleg dafür, dass das Arzneimittel das Ereignis verursacht.",
  fr: "Il s'agit d'une statistique de dépistage. De nombreuses associations médicament–événement sont examinées en même temps et la plupart remplissent ces critères ; les remplir est donc courant et ne prouve pas que le médicament provoque l'événement.",
  es: "Es una estadística de cribado. Se examinan a la vez muchas combinaciones de medicamento y evento y la mayoría cumple estos criterios; cumplirlos es habitual y no es una prueba de que el medicamento cause el evento.",
} as const;

export const SCREENING_KEY = "Memory.screening";

export type Locale = keyof typeof peopleWords;

/**
 * Words a `Memory` string must not contain. The screening sentence is exempt from the causal-word
 * list only as the complete value of `Memory.screening`; anywhere else, or with any change, it fails.
 */
export function memoryWordViolations(
  key: string,
  value: string,
  locale: Locale,
): string[] {
  const people = findForbiddenPhrases(value, peopleWords[locale]);
  const exempt = key === SCREENING_KEY && value === allowedScreening[locale];
  const causal = exempt ? [] : findForbiddenPhrases(value, causalWords[locale]);
  return [...people, ...causal];
}

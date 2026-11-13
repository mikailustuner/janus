/**
 * View model of the validation studies (researcher area). The numbers come from
 * validation.generated.json (scripts/gen-validation.mjs); this file only formats them for a
 * locale. A card added later (model kit precision, model kit gate) adds a key to the generated
 * file and one entry to CARDS.
 */
import generated from "./validation.generated.json";

export const VALIDATION = generated;
export const CARDS = ["cascade", "faers"] as const;
export type CardKey = (typeof CARDS)[number];

export interface Estimate {
  low: number;
  high: number;
  estimate: number;
}

/** A share as a percent ("26 %"), with the locale's own spacing and sign. */
export function percent(x: number, locale: string, digits = 0): string {
  return new Intl.NumberFormat(locale, {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(x);
}

/** A number with fixed decimals ("0.74"). */
export function decimal(x: number, locale: string, digits = 2): string {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(x);
}

/** Values of a proportion sentence: "k", "n", the estimate and its 95 % interval. */
export function proportionValues(
  m: { k: number; n: number } & Estimate,
  locale: string,
  digits = 3,
) {
  const nf = new Intl.NumberFormat(locale);
  return {
    k: nf.format(m.k),
    n: nf.format(m.n),
    estimate: decimal(m.estimate, locale, digits),
    low: decimal(m.low, locale, digits),
    high: decimal(m.high, locale, digits),
  };
}

/** Values of a share sentence: the percent estimate and its interval ends. */
export function shareValues(m: Estimate, locale: string, digits = 0) {
  return {
    estimate: percent(m.estimate, locale, digits),
    low: percent(m.low, locale, digits),
    high: percent(m.high, locale, digits),
  };
}

/** Values of the calibration line shown next to every reporting ratio. */
export function calibrationValues(locale: string) {
  const a = VALIDATION.faers.auc;
  return {
    auc: decimal(a.estimate, locale),
    low: decimal(a.low, locale),
    high: decimal(a.high, locale),
  };
}

/** Whether a pre-registered hypothesis was met, as a message key. */
export const hypothesisKey = (met: boolean) =>
  met ? "ValidationStudies.met" : "ValidationStudies.notMet";

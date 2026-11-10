/**
 * Display of strength codes (pharmacologist F7): codes are in micrograms; a whole multiple of
 * 1000 µg is shown in mg so the value reads as printed on most boxes. IU unchanged.
 */
import type { StrengthCode } from "./model";

export function strengthParts(code: StrengthCode): {
  amount: number;
  unit: "mg" | "ug" | "IU";
} {
  const n = Number(code.amount);
  if (code.unit === "IU") return { amount: n, unit: "IU" };
  return Number.isInteger(n) && n % 1000 === 0
    ? { amount: n / 1000, unit: "mg" }
    : { amount: n, unit: "ug" };
}

/** Source id of the resolution data → attribution code of the presence answer. */
export const ATTRIBUTION_OF: Record<
  string,
  "titck" | "bdpm" | "cima" | "openfda" | "aifa" | "dpd"
> = {
  titck: "titck",
  eu_fr_bdpm: "bdpm",
  eu_es_cima: "cima",
  openfda_ndc: "openfda",
  eu_it_aifa: "aifa",
  ca_dpd: "dpd",
};
/** Fixed source order of the answer (design §3.2): TR, EU-FR, EU-ES, EU-DE, US, EU-IT, CA. */
export const SOURCE_COUNTRY = [
  "TR",
  "FR",
  "ES",
  "DE",
  "US",
  "IT",
  "CA",
] as const;

/**
 * Strength typed from the box (medication-passport design §6.6, DP21, accepted by the owner on
 * 2026-11-08; P21). The same rule as `entry_code` in `apps/api/janus/passport/strength.py`: an
 * amount with a decimal point or comma (at most six decimals), a unit (mg, g, µg, IU) and "per
 * tablet, capsule or unit" or "per mL"; mass in micrograms, exact, no rounding. An amount like
 * "1,000" or "1.000" is refused: it is a thousands group in one language and a decimal in another.
 * The values stay in the browser and are labelled "as entered from the box" wherever used.
 */
import { AMOUNT, type StrengthCode } from "./model";

export const ENTRY_UNITS = { mg: 3, g: 6, ug: 0, IU: 0 } as const; // power of ten to micrograms
export const ENTRY_BASES = ["unit", "mL"] as const;
export type EntryUnit = keyof typeof ENTRY_UNITS;
export type EntryBasis = (typeof ENTRY_BASES)[number];

const ZERO = BigInt(0);
const TEN = BigInt(10);
const ENTRY = /^([0-9]{1,9})(?:[.,]([0-9]{1,6}))?$/;

/** Canonical decimal of `digits × 10^-places` (places ≤ 6), or null outside the request pattern. */
function canonical(digits: bigint, places: number): string | null {
  if (digits <= ZERO) return null;
  const scale = TEN ** BigInt(places);
  const whole = (digits / scale).toString();
  const frac = (digits % scale)
    .toString()
    .padStart(places, "0")
    .replace(/0+$/, "");
  const text = frac ? `${whole}.${frac}` : whole;
  return AMOUNT.test(text) ? text : null;
}

export function strengthFromEntry(
  amount: string,
  unit: string,
  basis: string,
): StrengthCode | null {
  const m = ENTRY.exec(amount.replace(/^ +| +$/g, ""));
  if (!m || !Object.hasOwn(ENTRY_UNITS, unit)) return null;
  if (!(ENTRY_BASES as readonly string[]).includes(basis)) return null;
  const [, whole, frac] = m;
  if (frac !== undefined && frac.length === 3 && BigInt(whole!) !== ZERO)
    return null;
  const places = frac?.length ?? 0;
  const power = ENTRY_UNITS[unit as EntryUnit];
  const digits = BigInt(`${whole}${frac ?? ""}`) * TEN ** BigInt(power);
  const text = canonical(digits, places);
  if (text === null) return null;
  return {
    amount: text,
    unit: unit === "IU" ? "IU" : "ug",
    basis: basis as EntryBasis,
  };
}

/**
 * The lot rule of the recall check, on the device (recall-check Req 5, design §9).
 *
 * The lot of a scanned box never leaves the browser: the API is asked by NDC only and answers
 * with each record's lot codes; the comparison happens here. Same normalisation as
 * `janus.recalls.codes.normalise_lot` (ASCII letters and digits, upper-cased); `LOT_EXAMPLES` is
 * the table both test suites check.
 */
export type LotMatch = "listed" | "not_listed" | "not_given";

/** GS1 character set 82, 1–20 characters: what AI (10) may hold. */
const GS1_LOT = /^[!"%&'()*+,\-./0-9:;<=>?A-Z_a-z]{1,20}$/;

export const LOT_EXAMPLES: readonly (readonly [string, string])[] = [
  ["AB1234", "AB1234"],
  ["ab-1234", "AB1234"],
  [" 37-883948 ", "37883948"],
  ["07282026@2", "072820262"],
  ["CC/004/24-25", "CC0042425"],
  ["Lot#", "LOT"],
  ["é12ß", "12"],
  ["---", ""],
];

export function normaliseLot(lot: string): string {
  return lot.replace(/[^0-9A-Za-z]/g, "").toUpperCase();
}

/** A lot read from AI (10) that can be kept: well-formed and with a letter or a digit. */
export function usableLot(value: string | undefined | null): string | null {
  if (!value || !GS1_LOT.test(value) || normaliseLot(value) === "") return null;
  return value;
}

/** Listed only when the normalised lot equals one of the record's lot codes: no prefix, no part. */
export function lotMatch(
  lot: string | null,
  lotCodes: readonly string[],
): LotMatch {
  if (lot === null) return "not_given";
  const code = normaliseLot(lot);
  return code !== "" && lotCodes.includes(code) ? "listed" : "not_listed";
}

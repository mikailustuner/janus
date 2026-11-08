/**
 * Item identity (medication-passport design §6.2, DP13): the same box added twice is one item.
 * - a product with a code read from the box: `source | code kind | code`;
 * - a product without a code (picked by name): `source | keys | strength codes | form | name`;
 * - a box typed by name (Germany and others): `country or region | name | keys | name`.
 * Box names are compared folded (case, accents, spacing), so "Demoamlo 5 mg" and "DEMOAMLO 5mg "
 * differ only by the space before "mg".
 */
import type { PassportItem, StrengthCode } from "./model";

export function fold(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

/** The item's distinct ingredient keys, sorted. */
export function itemKeys(item: Pick<PassportItem, "ingredients">): string[] {
  const keys = new Set<string>();
  for (const ing of item.ingredients) if (ing.key) keys.add(ing.key);
  return [...keys].sort();
}

const codeText = (s: StrengthCode | null) =>
  s ? `${s.amount}${s.unit}/${s.basis}` : "-";

export function itemIdentity(item: PassportItem): string {
  const keys = itemKeys(item).join("+");
  if ("entered_by_name" in item.source)
    return [
      item.origin.country ?? item.origin.region,
      "name",
      keys,
      fold(item.boxName),
    ].join("|");
  if (item.code)
    return [item.source.source_id, item.code.kind, item.code.value].join("|");
  const strengths = [...item.ingredients]
    .map((i) => `${i.key ?? "-"}=${codeText(i.strength)}`)
    .sort()
    .join(",");
  return [
    item.source.source_id,
    keys,
    strengths,
    item.doseForm?.group ?? "-",
    fold(item.boxName),
  ].join("|");
}

/**
 * Merging lists (medication-passport design §6.2, Req 1.4, P1). A list is a set of items keyed by
 * identity, kept in a deterministic display order (origin, folded box name, identity). Adding an
 * item whose identity is already present adds its box count and keeps the earlier known start
 * month. When two items of the same identity differ in other fields (two devices, two entries),
 * the merged item takes those fields from the smaller of the two by a fixed comparison, so the
 * result never depends on the order in which items or lists were added.
 */
import { fold, itemIdentity } from "./identity";
import type { PassportItem } from "./model";

const REGION_ORDER = ["TR", "EU", "US", "OTHER"] as const;
const COUNTRY_ORDER = ["TR", "FR", "ES", "DE", "US"] as const;

const cmpText = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

/** The fields that decide which of two same-identity items supplies the merged fields. */
function body(item: PassportItem): string {
  const { boxes, started, id, ...rest } = item;
  void boxes;
  void started;
  return JSON.stringify(rest) + "\u0000" + id;
}

export function earlierMonth(
  a: string | null,
  b: string | null,
): string | null {
  if (a === null) return b;
  if (b === null) return a;
  return a < b ? a : b;
}

export function displayOrder(a: PassportItem, b: PassportItem): number {
  const r =
    REGION_ORDER.indexOf(a.origin.region) -
    REGION_ORDER.indexOf(b.origin.region);
  if (r !== 0) return r;
  const c =
    (a.origin.country ? COUNTRY_ORDER.indexOf(a.origin.country) : 9) -
    (b.origin.country ? COUNTRY_ORDER.indexOf(b.origin.country) : 9);
  if (c !== 0) return c;
  return (
    cmpText(fold(a.boxName), fold(b.boxName)) ||
    cmpText(itemIdentity(a), itemIdentity(b))
  );
}

function combine(a: PassportItem, b: PassportItem): PassportItem {
  const first = cmpText(body(a), body(b)) <= 0 ? a : b;
  return {
    ...first,
    boxes: a.boxes + b.boxes,
    started: earlierMonth(a.started, b.started),
  };
}

/** Adds one item (or one more box of an item already on the list). */
export function addItem(
  list: readonly PassportItem[],
  item: PassportItem,
): PassportItem[] {
  const id = itemIdentity(item);
  let found = false;
  const out = list.map((x) => {
    if (found || itemIdentity(x) !== id) return x;
    found = true;
    return combine(x, item);
  });
  if (!found) out.push(item);
  return out.sort(displayOrder);
}

/** The union of two lists; same-identity items become one with the summed box count. */
export function mergeLists(
  a: readonly PassportItem[],
  b: readonly PassportItem[],
): PassportItem[] {
  return b.reduce<PassportItem[]>(
    (acc, item) => addItem(acc, item),
    [...a].reduce<PassportItem[]>((acc, item) => addItem(acc, item), []),
  );
}

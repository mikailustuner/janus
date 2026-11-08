/**
 * Presence request builder (medication-passport design §6.4, Req 9.1, 4.3, P18). The bodies hold
 * ingredient keys, strength codes and dose-form groups only: no box name, code, id, origin, count
 * or month. Identical item queries are sent once and fanned back to every item that asked them;
 * more than 50 items or 50 distinct keys are split into consecutive requests.
 *
 * An item is sent only when every ingredient has a key (DP24): with an unrecognised ingredient the
 * known keys alone would describe a different, smaller product, so "present" would overstate.
 */
import { isChecked } from "./duplicates";
import { itemKeys } from "./identity";
import {
  MAX_INGREDIENTS,
  MAX_ITEMS,
  MAX_KEYS,
  type IngredientIn,
  type ItemIn,
  type ItemOut,
  type PassportItem,
  type PresenceIn,
  type PresenceOut,
  type SourceOut,
} from "./model";

export type NotSent = "homeopathic" | "no_key" | "partial" | "too_many";

export function notSentReason(item: PassportItem): NotSent | null {
  if (item.homeopathic) return "homeopathic";
  if (!isChecked(item)) return "no_key";
  if (item.ingredients.some((i) => i.key === null)) return "partial";
  if (itemKeys(item).length > MAX_INGREDIENTS) return "too_many";
  return null;
}

/** The query of one item: distinct keys, sorted, with a strength only for a key listed once. */
export function itemQuery(item: PassportItem): ItemIn {
  const ingredients: IngredientIn[] = itemKeys(item).map((key) => {
    const lines = item.ingredients.filter((i) => i.key === key);
    const strength = lines.length === 1 ? lines[0]!.strength : null;
    return strength ? { key, strength: { ...strength } } : { key };
  });
  return item.doseForm
    ? { ingredients, dose_form: item.doseForm.group }
    : { ingredients };
}

export interface BuiltRequests {
  bodies: PresenceIn[];
  /** item id → position of its query: request number and item index in that request. */
  index: Map<string, { request: number; item: number }>;
  notSent: Map<string, NotSent>;
}

export function buildPresenceRequests(
  list: readonly PassportItem[],
): BuiltRequests {
  const notSent = new Map<string, NotSent>();
  const queries = new Map<string, ItemIn>(); // query text → query, in first-seen order
  const queryOf = new Map<string, string>(); // item id → query text
  for (const item of list) {
    const reason = notSentReason(item);
    if (reason) {
      notSent.set(item.id, reason);
      continue;
    }
    const q = itemQuery(item);
    const text = JSON.stringify(q);
    if (!queries.has(text)) queries.set(text, q);
    queryOf.set(item.id, text);
  }
  const bodies: PresenceIn[] = [];
  const position = new Map<string, { request: number; item: number }>();
  let keys = new Set<string>();
  for (const [text, q] of queries) {
    const current = bodies.at(-1);
    const added = q.ingredients.filter((i) => !keys.has(i.key)).length;
    if (
      !current ||
      current.items.length >= MAX_ITEMS ||
      keys.size + added > MAX_KEYS
    ) {
      bodies.push({ items: [] });
      keys = new Set();
    }
    const body = bodies.at(-1)!;
    for (const i of q.ingredients) keys.add(i.key);
    position.set(text, { request: bodies.length - 1, item: body.items.length });
    body.items.push(q);
  }
  const index = new Map<string, { request: number; item: number }>();
  for (const [id, text] of queryOf) index.set(id, position.get(text)!);
  return { bodies, index, notSent };
}

export interface ItemAnswer {
  item: ItemOut;
  sources: SourceOut[];
  dataset_version: string;
  notices: PresenceOut["notices"];
}

/** Every sent item's answer, from the responses in request order (same length as `bodies`). */
export function fanBack(
  built: BuiltRequests,
  outs: readonly PresenceOut[],
): Map<string, ItemAnswer> {
  const out = new Map<string, ItemAnswer>();
  for (const [id, pos] of built.index) {
    const res = outs[pos.request];
    const item = res?.items[pos.item];
    if (!res || !item) continue;
    out.set(id, {
      item,
      sources: res.sources,
      dataset_version: res.dataset_version,
      notices: res.notices,
    });
  }
  return out;
}

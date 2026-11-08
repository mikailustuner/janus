/**
 * Collective Memory keys of the list (medication-passport design §6.5, Req 11, P20): the sorted
 * distinct keys of the checked items. Box counts, item order and duplicates change nothing. Above
 * 20 keys no request is built until the user has chosen which ingredients to look at (Req 11.2):
 * nothing is dropped silently.
 */
import { isChecked } from "./duplicates";
import { itemKeys } from "./identity";
import type { PassportItem } from "./model";

export const MEMORY_MAX_KEYS = 20;

export function memoryKeys(list: readonly PassportItem[]): string[] {
  const keys = new Set<string>();
  for (const item of list)
    if (isChecked(item)) for (const k of itemKeys(item)) keys.add(k);
  return [...keys].sort();
}

export type MemoryRequests =
  | {
      kind: "ready";
      keys: string[];
      combination: { ingredients: string[]; scope: "any" } | null;
      regions: { ingredients: string[] } | null;
    }
  | { kind: "needs_selection"; keys: string[] }
  | { kind: "none" };

/**
 * The bodies of `POST /memory/combination` (2–20 keys, scope `any`) and `POST /memory/regions`
 * (1–20 keys). `selection` is the user's choice when the list has more than 20 keys; keys that
 * are not on the list are ignored.
 */
export function memoryRequests(
  list: readonly PassportItem[],
  selection?: readonly string[],
): MemoryRequests {
  const all = memoryKeys(list);
  let keys = all;
  if (all.length > MEMORY_MAX_KEYS) {
    const chosen = [...new Set(selection ?? [])]
      .filter((k) => all.includes(k))
      .sort();
    if (chosen.length === 0 || chosen.length > MEMORY_MAX_KEYS)
      return { kind: "needs_selection", keys: all };
    keys = chosen;
  }
  if (keys.length === 0) return { kind: "none" };
  return {
    kind: "ready",
    keys,
    combination:
      keys.length >= 2 ? { ingredients: [...keys], scope: "any" } : null,
    regions: { ingredients: [...keys] },
  };
}

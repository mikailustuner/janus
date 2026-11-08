/**
 * Duplicate-ingredient groups (medication-passport design §6.3, Req 1.2, 1.3, 1.5, 1.6, P2, DP14).
 * One group per ingredient key carried by two or more distinct checked items; a key repeated
 * inside one item (two salt lines) is not a duplicate. Groups are information only: the list is
 * not changed and no item is singled out.
 */
import { itemKeys } from "./identity";
import type { PassportItem } from "./model";

/** Checked: not homeopathic, with at least one ingredient key (Req 1.5, 1.6). */
export const isChecked = (item: PassportItem): boolean =>
  !item.homeopathic && itemKeys(item).length > 0;

export interface DuplicateGroup {
  key: string;
  items: string[]; // item ids, sorted
}

export function duplicateGroups(
  list: readonly PassportItem[],
): DuplicateGroup[] {
  const byKey = new Map<string, Set<string>>();
  for (const item of list) {
    if (!isChecked(item)) continue;
    for (const key of itemKeys(item)) {
      const ids = byKey.get(key) ?? new Set<string>();
      ids.add(item.id);
      byKey.set(key, ids);
    }
  }
  return [...byKey]
    .filter(([, ids]) => ids.size >= 2)
    .map(([key, ids]) => ({ key, items: [...ids].sort() }))
    .sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
}

/** The groups that name one item, for the chip on its card. */
export function groupsOf(
  groups: readonly DuplicateGroup[],
  id: string,
): DuplicateGroup[] {
  return groups.filter((g) => g.items.includes(id));
}

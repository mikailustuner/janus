/**
 * Passport slots (experience design §15, DP25, Req 26.2): render nothing until the
 * medication-passport spec provides them under src/passport/. The shell does not change.
 */
import type { Item } from "@/store/list";

export function ItemBadges(props: { item: Item }) {
  void props;
  return null;
}
export function ItemDetailExtra(props: { item: Item }) {
  void props;
  return null;
}
export function ListSummaryExtra(props: { items: readonly Item[] }) {
  void props;
  return null;
}

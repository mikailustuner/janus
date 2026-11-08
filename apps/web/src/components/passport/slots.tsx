"use client";
/**
 * Passport slots (experience design §15, DP25, Req 26.2), filled by medication-passport: a link
 * from each medicine to its Passport detail, and the duplicate-ingredient notice over the list
 * (information only, no action). The shell does not change.
 */
import { ButtonLink } from "@/components/ui";
import { duplicateGroups } from "@/passport/duplicates";
import { mergeLists } from "@/passport/merge";
import { fromListItem } from "@/passport/model";
import type { Item } from "@/store/list";
import { useT } from "@/theme/words";

export function ItemBadges({ item }: { item: Item }) {
  const t = useT();
  return (
    <ButtonLink
      href={`/passport/item#${encodeURIComponent(item.id)}`}
      variant="quiet"
      className="w-fit px-2 text-sm"
    >
      {t("Passport.fromMedicine")}
      <span className="sr-only">: {item.boxName}</span>
    </ButtonLink>
  );
}
export function ItemDetailExtra(props: { item: Item }) {
  void props;
  return null;
}
export function ListSummaryExtra({ items }: { items: readonly Item[] }) {
  const t = useT();
  const groups = duplicateGroups(
    mergeLists(
      items.map((i) => fromListItem(i, (_k, p) => p)),
      [],
    ),
  );
  if (groups.length === 0) return null;
  return (
    <div className="card flex flex-wrap items-center justify-between gap-3 p-3">
      <p className="font-bold">
        {t("Passport.duplicate.summary", { count: groups.length })}
      </p>
      <ButtonLink href="/passport" variant="secondary">
        {t("Passport.duplicate.chip")}
      </ButtonLink>
    </div>
  );
}

"use client";
/**
 * The Passport list (design §8 "Passport list", Req 1, 10.1, 10.3, 11): every box with its
 * origin, source and date (or "entered by name"; Germany: no open product database), ingredient
 * names, box count, the homeopathic and "not checked" labels, the duplicate-ingredient chip on
 * each box of a group (information only: no action), and the Collective Memory entry point.
 * Names wrap, never truncated; from 1024 px two columns of cards beside an aside.
 */
import { useLocale } from "next-intl";

import { StateView } from "@/components/StateView";
import { LargeTitle, SummaryCard } from "@/components/cards";
import { ChevronIcon } from "@/components/icons";
import { ButtonLink, Chip } from "@/components/ui";
import { formatDate } from "@/components/format";
import { useT, type Translate } from "@/theme/words";
import { Link } from "@/i18n/navigation";

import { duplicateGroups, groupsOf, type DuplicateGroup } from "../duplicates";
import { ATTRIBUTION_OF } from "../format";
import { memoryRequests } from "../memory-keys";
import type { PassportItem } from "../model";
import { notSentReason } from "../request";
import { CopyIcon } from "./icons";
import { usePassport } from "./usePassport";

export function sourceLine(
  t: Translate,
  item: PassportItem,
  locale: string,
): string {
  if ("entered_by_name" in item.source)
    return item.origin.country === "DE"
      ? t("Passport.germanyByName")
      : t("Passport.enteredByName");
  const code = ATTRIBUTION_OF[item.source.source_id];
  return t("Common.sourceLine", {
    source: code ? t(`Passport.sourceName.${code}`) : item.source.source_id,
    date: formatDate(item.source.snapshot_date, locale),
  });
}

function DuplicateChip({
  group,
  items,
}: {
  group: DuplicateGroup;
  items: readonly PassportItem[];
}) {
  const t = useT();
  const locale = useLocale();
  const named = items.filter((i) => group.items.includes(i.id));
  const ingredient =
    named[0]?.ingredients.find((g) => g.key === group.key)?.label ?? group.key;
  return (
    <div className="flex flex-col gap-1 rounded-[var(--radius-card)] bg-chip p-3 text-chip-fg">
      <p className="flex items-center gap-2 font-bold">
        <CopyIcon />
        {t("Passport.duplicate.chip")}
      </p>
      <p>
        {t("Passport.duplicate.text", {
          ingredient,
          boxes: new Intl.ListFormat(locale, { type: "conjunction" }).format(
            named.map((i) => i.boxName),
          ),
          count: named.length,
        })}
      </p>
    </div>
  );
}

function ItemCard({
  item,
  items,
  groups,
}: {
  item: PassportItem;
  items: readonly PassportItem[];
  groups: readonly DuplicateGroup[];
}) {
  const t = useT();
  const locale = useLocale();
  const reason = notSentReason(item);
  const headingId = `passport-${item.id}`;
  return (
    <SummaryCard
      as="li"
      id={headingId}
      title={item.boxName}
      eyebrow={
        <Chip>
          {t(`Passport.origin.${item.origin.country ?? item.origin.region}`)}
        </Chip>
      }
      summary={
        <p className="text-fg">
          <span className="sr-only">{t("Passport.ingredients")}: </span>
          {new Intl.ListFormat(locale, { type: "unit" }).format(
            item.ingredients.map((g) => g.label),
          )}
        </p>
      }
      className="[overflow-wrap:anywhere]"
    >
      <ul className="grouped-plain border-t border-line text-sm">
        <li className="text-muted">{sourceLine(t, item, locale)}</li>
        <li>{t("Passport.boxes", { count: item.boxes })}</li>
        {reason === "homeopathic" ? (
          <li className="font-bold">{t("Passport.homeopathic")}</li>
        ) : reason ? (
          <li className="font-bold">{t(`Passport.notCheckable.${reason}`)}</li>
        ) : null}
      </ul>
      {groupsOf(groups, item.id).map((g) => (
        <DuplicateChip key={g.key} group={g} items={items} />
      ))}
      <Link
        href={`/passport/item#${encodeURIComponent(item.id)}`}
        className="-mx-4 mt-auto -mb-4 flex min-h-13 items-center justify-between gap-3 rounded-b-[var(--radius-card)] border-t border-line px-4 font-bold text-accent no-underline transition-colors duration-150 hover:bg-chip sm:-mx-5 sm:-mb-5 sm:px-5"
      >
        <span>
          {t("Passport.open")}
          <span className="sr-only">: {item.boxName}</span>
        </span>
        <ChevronIcon size={20} className="shrink-0" />
      </Link>
    </SummaryCard>
  );
}

/** The list screen's body for a given list (also used by the render tests). */
export function PassportListBody({
  items,
  demo,
}: {
  items: readonly PassportItem[];
  demo: string | null;
}) {
  const t = useT();
  const groups = duplicateGroups(items);
  const memory = memoryRequests(items);
  const boxes = items.reduce((s, i) => s + i.boxes, 0);
  return (
    <>
      <LargeTitle
        title={t("Passport.title")}
        summary={
          items.length
            ? t("Cards.passport.summary", { items: items.length, boxes })
            : undefined
        }
      />
      <p className="max-w-[72ch]">{t("Passport.intro")}</p>
      {demo === "cologne" ? (
        <p className="text-sm text-muted">{t("Passport.demo.intro")}</p>
      ) : null}
      {items.length === 0 ? (
        <StateView
          state="empty"
          message={t("Passport.states.empty")}
          action={
            <ButtonLink href="/scan">
              {t("Passport.states.emptyAction")}
            </ButtonLink>
          }
        />
      ) : (
        <div className="grid gap-group lg:grid-cols-[minmax(0,1fr)_minmax(280px,340px)] lg:items-start">
          <ul className="grid min-w-0 gap-4 xl:grid-cols-2">
            {items.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                items={items}
                groups={groups}
              />
            ))}
          </ul>
          <aside className="flex min-w-0 flex-col gap-group lg:sticky lg:top-4">
            {groups.length > 0 ? (
              <p className="card flex items-center gap-2 p-5 font-bold">
                <CopyIcon />
                {t("Passport.duplicate.summary", { count: groups.length })}
              </p>
            ) : null}
            {memory.kind !== "none" ? (
              <SummaryCard
                title={t("Passport.memory.entry")}
                id="passport-memory"
              >
                <p>{t("Passport.memory.intro")}</p>
                {memory.kind === "needs_selection" ? (
                  <p>{t("Passport.memory.tooMany")}</p>
                ) : null}
                <ButtonLink
                  href="/memory"
                  variant="secondary"
                  className="w-fit"
                >
                  {t("Passport.memory.open")}
                </ButtonLink>
              </SummaryCard>
            ) : null}
            <p className="card p-5 text-sm">{t("Passport.listingsOnly")}</p>
          </aside>
        </div>
      )}
    </>
  );
}

export function PassportList() {
  const view = usePassport();
  if (!view.ready) return <StateView state="loading" />;
  return <PassportListBody items={view.items} demo={view.demo} />;
}

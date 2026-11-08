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
import { ButtonLink, Card, Chip, PageTitle } from "@/components/ui";
import { formatDate } from "@/components/format";
import { useT, type Translate } from "@/theme/words";

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
    <Card
      as="li"
      aria-labelledby={headingId}
      className="[overflow-wrap:anywhere]"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 id={headingId} className="min-w-0 text-lg leading-snug font-bold">
          {item.boxName}
        </h2>
        <Chip>
          {t(`Passport.origin.${item.origin.country ?? item.origin.region}`)}
        </Chip>
      </div>
      <p className="text-sm text-muted">{sourceLine(t, item, locale)}</p>
      <div>
        <p className="text-sm font-bold">{t("Passport.ingredients")}</p>
        <ul className="flex flex-col">
          {item.ingredients.map((g, i) => (
            <li key={i}>{g.label}</li>
          ))}
        </ul>
      </div>
      <p className="text-sm">{t("Passport.boxes", { count: item.boxes })}</p>
      {reason === "homeopathic" ? (
        <p className="font-bold">{t("Passport.homeopathic")}</p>
      ) : reason ? (
        <p className="font-bold">{t(`Passport.notCheckable.${reason}`)}</p>
      ) : null}
      {groupsOf(groups, item.id).map((g) => (
        <DuplicateChip key={g.key} group={g} items={items} />
      ))}
      <ButtonLink
        href={`/passport/item#${encodeURIComponent(item.id)}`}
        variant="secondary"
        className="w-fit"
      >
        {t("Passport.open")}
        <span className="sr-only">: {item.boxName}</span>
      </ButtonLink>
    </Card>
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
      <PageTitle eyebrow={t("Passport.boxes", { count: boxes })}>
        {t("Passport.title")}
      </PageTitle>
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
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(280px,340px)] lg:items-start">
          <ul className="grid min-w-0 gap-3 xl:grid-cols-2">
            {items.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                items={items}
                groups={groups}
              />
            ))}
          </ul>
          <aside className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-4">
            {groups.length > 0 ? (
              <Card>
                <p className="flex items-center gap-2 font-bold">
                  <CopyIcon />
                  {t("Passport.duplicate.summary", { count: groups.length })}
                </p>
              </Card>
            ) : null}
            {memory.kind !== "none" ? (
              <Card>
                <h2 className="text-lg font-semibold">
                  {t("Passport.memory.entry")}
                </h2>
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
              </Card>
            ) : null}
            <p className="card p-4 text-sm">{t("Passport.listingsOnly")}</p>
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

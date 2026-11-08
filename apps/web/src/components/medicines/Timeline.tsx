"use client";
/**
 * The timeline (Req 13.3, P23): start months in time order, a separate lane for unknown starts,
 * and after an evaluation each finding as a link from its first medicine to its second, with the
 * months between as returned by the API. The bars only place the start months on an axis.
 */
import { useLocale } from "next-intl";

import type { CascadeResult } from "@/api/contracts";
import { formatMonth } from "@/components/format";
import { StateView } from "@/components/StateView";
import { ButtonLink, Card, PageTitle, SectionTitle } from "@/components/ui";
import { inputKey, currentMonth, toEvaluateIn } from "@/flow/evaluate";
import { resultCache, useSession } from "@/flow/janus";
import { monthIndex, timeline } from "@/flow/timeline";
import { useT } from "@/theme/words";

export function Timeline() {
  const t = useT();
  const locale = useLocale();
  const session = useSession();
  if (!session.ready) return <StateView state="loading" />;
  const { items } = session;
  const built = toEvaluateIn(items);
  const result = built.ok
    ? (resultCache.get<CascadeResult>(inputKey(built.body)) ?? null)
    : null;
  const model = timeline(items, result);
  const end = result?.as_of_month ?? currentMonth();
  const start = model.range?.first ?? end;
  const span = Math.max(1, monthIndex(end) - monthIndex(start));
  const name = (i: number) => items[i]?.boxName ?? "";

  return (
    <>
      <PageTitle>{t("Timeline.title")}</PageTitle>
      <p>{t("Timeline.intro")}</p>
      {model.dated.length === 0 ? (
        <StateView
          state="empty"
          message={t("Timeline.empty")}
          action={
            <ButtonLink href="/medicines">{t("Medicines.title")}</ButtonLink>
          }
        />
      ) : (
        <Card>
          <ol className="flex flex-col gap-3">
            {model.dated.map(({ item, started }) => {
              const left =
                ((monthIndex(started) - monthIndex(start)) / span) * 100;
              return (
                <li
                  key={item}
                  className="grid grid-cols-1 gap-1 sm:grid-cols-[minmax(0,12rem)_1fr] sm:items-center sm:gap-3"
                >
                  <span className="text-sm">
                    <span className="font-bold">{name(item)}</span>
                    <span className="block text-muted">
                      {formatMonth(started, locale)}
                    </span>
                  </span>
                  <span
                    className="relative block h-3 rounded-full bg-chip"
                    aria-hidden
                  >
                    <span
                      className="absolute top-0 right-0 bottom-0 rounded-full bg-accent"
                      style={{ left: `${Math.min(97, left)}%` }}
                    />
                  </span>
                </li>
              );
            })}
          </ol>
          <p
            className="mono flex justify-between text-xs text-muted"
            aria-hidden
          >
            <span>{formatMonth(start, locale)}</span>
            <span>{formatMonth(end, locale)}</span>
          </p>
        </Card>
      )}
      {model.undated.length ? (
        <Card>
          <SectionTitle>{t("Timeline.unknownLane")}</SectionTitle>
          <ul className="list-disc pl-5">
            {model.undated.map((i) => (
              <li key={i}>{name(i)}</li>
            ))}
          </ul>
        </Card>
      ) : null}
      {model.links.length ? (
        <Card>
          <ul className="flex flex-col gap-2">
            {model.links.map((l) => {
              const index = l.from.map(name).join(", ");
              const marker = l.to.map(name).join(", ");
              return (
                <li key={l.findingId}>
                  {l.months !== null
                    ? t("Timeline.link", { marker, index, months: l.months })
                    : l.timing === "same_month"
                      ? t("Timeline.linkSameMonth", { marker, index })
                      : t("Timeline.linkUnknown", { marker, index })}
                </li>
              );
            })}
          </ul>
        </Card>
      ) : null}
    </>
  );
}

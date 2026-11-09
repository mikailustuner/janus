"use client";
/**
 * The evidence of a finding with the integrity line (Req 15, P30, Req 29): two stat tiles over the
 * integrity line (its sentences stay visible), then the cited sources and the sources not used as
 * grouped rows. Retracted sources only in the list of sources not used, with the zombie stamp
 * (Night Pharmacy) or a plain "Retracted" label.
 */
import { useLocale } from "next-intl";

import type { EvidenceItem, EvidenceResolution } from "@/api/contracts";
import {
  GroupedList,
  StatGrid,
  StatTile,
  SummaryCard,
} from "@/components/cards";
import { formatCount, formatDate } from "@/components/format";
import { evidenceView } from "@/flow/integrity";
import { useT, useThemeWord } from "@/theme/words";

function SourceRow({ item }: { item: EvidenceItem }) {
  const t = useT();
  const locale = useLocale();
  const status = item.integrity?.status;
  return (
    <li className="flex min-w-0 flex-col gap-1">
      <span className="font-bold">
        {item.title ?? item.source?.name ?? item.id}
      </span>
      {item.doi ? <span className="mono text-sm">doi:{item.doi}</span> : null}
      {item.locator ? (
        <span className="text-sm text-muted">{item.locator}</span>
      ) : null}
      <span className="text-sm text-muted">
        {status
          ? t(`Evidence.status.${status}`)
          : t("Evidence.notCheckedByDoi")}
        {item.integrity?.checked_at
          ? ` · ${t("Evidence.checkedOn", { date: formatDate(item.integrity.checked_at, locale) })}`
          : ""}
        {item.freshness && item.freshness.state !== "not_applicable"
          ? ` · ${t(`Evidence.freshness.${item.freshness.state}`, { days: item.freshness.age_days })}`
          : ""}
      </span>
      {item.integrity?.notices.map((n, i) => (
        <span key={i} className="text-sm">
          {n.notice_url ? (
            <a
              href={n.notice_url}
              data-inline="true"
              className="underline underline-offset-4"
              rel="noreferrer noopener"
              target="_blank"
            >
              {t("Evidence.notice", {
                type: t(
                  `Evidence.noticeType.${["correction", "expression_of_concern", "retraction"].includes(n.type) ? n.type : "other"}`,
                ),
                date: n.date ? formatDate(n.date, locale) : "",
              })}
            </a>
          ) : null}
        </span>
      ))}
      {item.roots.length ? (
        <span className="text-sm text-muted">
          {t("Evidence.roots")}:{" "}
          {item.roots.map((r) => r.title ?? r.id).join("; ")}
        </span>
      ) : null}
    </li>
  );
}

export function EvidenceBody({
  resolution,
}: {
  resolution: EvidenceResolution;
}) {
  const t = useT();
  const w = useThemeWord();
  const locale = useLocale();
  const v = evidenceView(resolution);
  const l = v.line;
  return (
    <SummaryCard
      title={t("Evidence.title")}
      id="evidence"
      data-testid="evidence"
    >
      {/* The integrity line's numbers as tiles; the sentences stay visible below (Req 15.2, DP53). */}
      <StatGrid>
        <StatTile
          value={formatCount(l.sources_total, locale)}
          label={t("Cards.label.sources", { count: l.sources_total })}
        />
        <StatTile
          value={formatCount(l.checked_by_doi, locale)}
          label={t("Cards.label.checkedByDoi", { count: l.checked_by_doi })}
        />
      </StatGrid>
      <div
        className="flex flex-col gap-1 rounded-[var(--radius-tile)] bg-chip p-3 text-sm text-chip-fg"
        data-testid="integrity-line"
      >
        {/* The sources sentence first: "no retracted source" never leads without its scope
            (safety audit F2, Req 15.2). */}
        <p>
          {t("Evidence.line.sources", {
            total: l.sources_total,
            checked: l.checked_by_doi,
          })}
        </p>
        <p>
          {t("Evidence.line.byStatus", {
            ok: l.by_status.ok,
            corrected: l.by_status.corrected,
            eoc: l.by_status.expression_of_concern,
            unknown: l.by_status.unknown,
          })}
        </p>
        {l.oldest_check && l.newest_check ? (
          <p>
            {t("Evidence.line.range", {
              first: formatDate(l.oldest_check, locale),
              last: formatDate(l.newest_check, locale),
            })}
          </p>
        ) : null}
        {l.stale_sources.map((s) => (
          <p key={s.source_id}>
            {t("Evidence.line.stale", {
              source: s.source_id,
              date: formatDate(s.snapshot_date, locale),
            })}
          </p>
        ))}
        {v.noRetracted ? (
          <p className="font-bold">{t("Evidence.line.noRetracted")}</p>
        ) : (
          <p>{t("Evidence.line.exceptions", { count: v.exceptions.length })}</p>
        )}
        <p>{t("Evidence.line.about")}</p>
      </div>
      <GroupedList
        plain
        level={3}
        header={t("Evidence.cited")}
        headingId="evidence-cited"
      >
        {v.used.map((i) => (
          <SourceRow key={i.id} item={i} />
        ))}
      </GroupedList>
      {v.excluded.length ? (
        <GroupedList
          plain
          level={3}
          header={t("Evidence.excluded")}
          headingId="evidence-excluded"
        >
          {v.excluded.map((e) => (
            <li
              key={e.id}
              className="flex flex-col gap-1"
              data-testid="excluded-source"
            >
              {e.stamp ? (
                <span
                  className="mono w-max -rotate-3 rounded-sm border-2 border-risk px-1.5 py-0.5 text-xs font-bold tracking-wider text-risk uppercase"
                  data-testid="retracted-stamp"
                >
                  {w("Evidence.stamp")}
                </span>
              ) : null}
              <span className="line-through">{e.item?.title ?? e.id}</span>
              <span className="text-sm">
                {t("Evidence.notUsed")} ({t(`Evidence.reason.${e.reason}`)})
              </span>
            </li>
          ))}
        </GroupedList>
      ) : null}
    </SummaryCard>
  );
}

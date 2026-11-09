"use client";
/**
 * One PIPC row of the FAERS onset table (research-tools Req 2.3; faers-onset-table design §7):
 * the count and the status first, then — only for `described` and `small_sample` rows — the median
 * with its exact 95 % interval and the middle half of the reports (chart and table), the
 * sensitivities and the Weibull shape where published; the date-quality counts, the row's
 * definition (class, event terms, routes, shared rows), the PIPC text as published, the row notes
 * and the caveats. The position is read from the URL fragment (a number 1-65, not personal data).
 */
import { useEffect, useMemo, useState } from "react";
import { useLocale } from "next-intl";

import {
  BackLink,
  GroupedList,
  LargeTitle,
  Row,
  StatGrid,
  StatTile,
  SummaryCard,
} from "@/components/cards";
import { StateView } from "@/components/StateView";
import { IntervalChart } from "@/components/timemachine/common";
import { useCall } from "@/flow/useCall";
import {
  POSITION,
  showsShape,
  showsMedian,
  type OnsetRow,
  type OnsetRowOut,
} from "@/research/onset";
import { linearAxis } from "@/timemachine/view";
import { useT } from "@/theme/words";
import { useVocabulary } from "@/vocabulary/use";

import {
  Caveats,
  OnsetFraming,
  patternTitle,
  useOnsetClient,
} from "./OnsetTable";

const REASONS = [
  "no_therapy_start",
  "start_date_partial",
  "event_date_missing",
  "negative_interval",
  "interval_over_max",
] as const;

/** The PIPC position after `#`; null when it is not 1-2 digits, undefined before the first read. */
function usePosition(): number | null | undefined {
  const [p, setP] = useState<number | null | undefined>(undefined);
  useEffect(() => {
    const read = () => {
      const v = location.hash.slice(1);
      setP(POSITION.test(v) ? Number(v) : null);
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  return p;
}

export function OnsetRowView() {
  const t = useT();
  const position = usePosition();
  const { client, recorded, failed } = useOnsetClient();
  const call = useCall(client && position ? () => client.row(position) : null, [
    client,
    position,
  ]);
  return (
    <>
      <BackLink href="/research/faers-onset">{t("Onset.title")}</BackLink>
      {position === null ? (
        <>
          <LargeTitle title={t("Onset.title")} />
          <StateView state="empty" message={t("Onset.errors.unknown")} />
        </>
      ) : failed || call.status === "error" ? (
        <>
          <LargeTitle title={t("Onset.title")} />
          <StateView
            state="error"
            messageKey={
              call.status === "error" ? call.error.messageKey : "Errors.generic"
            }
            retry={call.status === "error" ? call.retry : undefined}
          />
        </>
      ) : call.status !== "ok" ? (
        <>
          <LargeTitle title={t("Onset.title")} />
          <StateView state="loading" label={t("Onset.loading")} />
        </>
      ) : (
        <Detail out={call.data} recorded={recorded} />
      )}
    </>
  );
}

function Detail({
  out,
  recorded,
}: {
  out: OnsetRowOut;
  recorded: string | null;
}) {
  const t = useT();
  const vocab = useVocabulary();
  const locale = useLocale();
  const r = out.row;
  const nf = useMemo(
    () => new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }),
    [locale],
  );
  const pct = useMemo(
    () =>
      new Intl.NumberFormat(locale, {
        style: "percent",
        maximumFractionDigits: 1,
      }),
    [locale],
  );
  const eventLabel = vocab?.vocab.events[r.event_key]?.label ?? r.event_key;
  return (
    <>
      <LargeTitle
        eyebrow={t("Onset.rowEyebrow", { row: r.pipc_position })}
        title={patternTitle(t, vocab, r)}
        summary={t(`Onset.status.${r.status}`)}
        summaryTestId="onset-row-status"
      />
      <OnsetFraming recorded={recorded} />
      <SummaryCard
        id="onset-counts"
        title={t("Onset.detail.counts")}
        data-testid="onset-counts"
      >
        <StatGrid>
          <StatTile
            value={nf.format(r.candidate_reports)}
            label={t("Onset.cols.reports")}
            sentence={t("Onset.detail.reportsSentence", {
              count: r.candidate_reports,
            })}
          />
          <StatTile
            value={nf.format(r.reports_with_interval)}
            label={t("Onset.cols.interval")}
            sentence={t("Onset.detail.intervalSentence", {
              count: r.reports_with_interval,
            })}
          />
          {r.usable_share !== null ? (
            <StatTile
              value={pct.format(r.usable_share)}
              label={t("Onset.detail.usable")}
              sentence={t("Onset.detail.usableSentence", {
                share: pct.format(r.usable_share),
                n: nf.format(r.reports_with_interval),
                total: nf.format(r.candidate_reports),
              })}
            />
          ) : null}
        </StatGrid>
        {r.usable_share !== null ? (
          <p className="text-sm">
            {t("Onset.detail.usableLine", {
              n: nf.format(r.reports_with_interval),
              total: nf.format(r.candidate_reports),
            })}
          </p>
        ) : null}
        <p className="text-sm font-bold">{t("Onset.reportsNotPeople")}</p>
        <p data-testid="onset-status-text">
          {t(`Onset.statusLegend.${r.status}`)}
        </p>
      </SummaryCard>
      {showsMedian(r) ? <Statistics r={r} /> : null}
      <DateQuality r={r} />
      <GroupedList
        header={t("Onset.detail.definition")}
        headingId="onset-definition"
        data-testid="onset-definition"
      >
        <Row>
          <span className="text-sm text-muted">{t("Onset.detail.class")}</span>
          <span className="mono break-all">{r.index_class}</span>
        </Row>
        <Row>
          <span className="text-sm text-muted">{t("Onset.detail.event")}</span>
          <span>{eventLabel}</span>
          <span className="text-sm break-words">
            <span className="text-muted">{t("Onset.detail.terms")}: </span>
            <span lang="en">{r.event_pts.join(", ")}</span>
          </span>
        </Row>
        <Row>
          <span className="text-sm text-muted">{t("Onset.detail.routes")}</span>
          <span>
            {r.route_groups_counted
              .map((g) => t(`Onset.route.${g}`))
              .join(", ")}
          </span>
        </Row>
        {r.shared_with_positions.length ? (
          <Row data-testid="onset-shared">
            {t("Onset.detail.shared", {
              rows: r.shared_with_positions.join(", "),
            })}
          </Row>
        ) : null}
        <Row>
          <span className="text-sm text-muted">{t("Onset.detail.pipc")}</span>
          <span lang="en" className="break-words">
            {r.pipc_drug_a} → {r.pipc_adverse_event} → {r.pipc_drug_b} (
            {r.pipc_system}; {r.pipc_locator})
          </span>
        </Row>
      </GroupedList>
      {r.row_notes.length ? (
        <GroupedList
          header={t("Onset.detail.notes")}
          headingId="onset-notes"
          data-testid="onset-notes"
          footer={<p>{t("Onset.detail.notesFooter")}</p>}
        >
          {r.row_notes.map((n) => (
            <Row key={n.code}>
              <span lang="en" className="text-sm break-words">
                {n.note}
              </span>
            </Row>
          ))}
        </GroupedList>
      ) : null}
      <Caveats caveats={out.caveats} />
      <p className="text-sm break-words text-muted" lang="en">
        {out.meddra_notice}
      </p>
    </>
  );
}

function Statistics({ r }: { r: OnsetRow }) {
  const t = useT();
  const locale = useLocale();
  const nf = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
  const pct = new Intl.NumberFormat(locale, {
    style: "percent",
    maximumFractionDigits: 1,
  });
  if (
    r.median_days === null ||
    r.q25_days === null ||
    r.q75_days === null ||
    r.median_exact_ci_low_days === null ||
    r.median_exact_ci_high_days === null
  )
    return null;
  const axis = linearAxis([r.q75_days, r.median_exact_ci_high_days]);
  return (
    <SummaryCard
      id="onset-stats"
      title={t("Onset.detail.timing")}
      summary={t("Onset.detail.medianLine", {
        median: nf.format(r.median_days),
        low: nf.format(r.median_exact_ci_low_days),
        high: nf.format(r.median_exact_ci_high_days),
        coverage:
          r.median_exact_ci_coverage === null
            ? "—"
            : pct.format(r.median_exact_ci_coverage),
      })}
      data-testid="onset-stats"
    >
      {r.small_sample ? (
        <p className="font-bold" data-testid="onset-small-sample">
          {t("Onset.detail.smallSample", { count: r.reports_with_interval })}
        </p>
      ) : null}
      {r.median_reflects_zero_heaping ? (
        <p className="font-bold" data-testid="onset-heaping">
          {t("Onset.detail.heaping")}
        </p>
      ) : null}
      <p>
        {t("Onset.detail.iqrLine", {
          q25: nf.format(r.q25_days),
          q75: nf.format(r.q75_days),
        })}
      </p>
      <IntervalChart
        title={t("Onset.detail.chartTitle")}
        unit={t("Onset.detail.unit")}
        axis={axis}
        testId="onset-chart"
        legend={t("Onset.detail.chartLegend")}
        columns={[
          t("Onset.detail.colLow"),
          t("Onset.detail.colMedian"),
          t("Onset.detail.colHigh"),
        ]}
        rows={[
          {
            label: t("Onset.detail.iqr"),
            low: r.q25_days,
            mid: r.median_days,
            high: r.q75_days,
          },
          {
            label: t("Onset.detail.exactCi"),
            low: r.median_exact_ci_low_days,
            mid: r.median_days,
            high: r.median_exact_ci_high_days,
            tone: "muted",
          },
        ]}
      />
      <p className="text-sm font-bold">{t("Onset.detail.otherReadings")}</p>
      <ul
        className="flex list-disc flex-col gap-1 ps-5 text-sm"
        data-testid="onset-readings"
      >
        <li>
          {r.median_days_without_day_one !== null
            ? t("Onset.detail.withoutDayOne", {
                median: nf.format(r.median_days_without_day_one),
                n: nf.format(r.reports_without_day_one),
              })
            : t("Onset.detail.withoutDayOneOmitted")}
        </li>
        {r.median_days_distinct_date_pairs !== null ? (
          <li>
            {t("Onset.detail.distinctPairs", {
              median: nf.format(r.median_days_distinct_date_pairs),
            })}
          </li>
        ) : null}
        {r.median_days_earliest_class_start !== null ? (
          <li>
            {t("Onset.detail.earliestStart", {
              median: nf.format(r.median_days_earliest_class_start),
            })}
          </li>
        ) : null}
      </ul>
      {showsShape(r) && r.weibull_shape_class ? (
        <p className="text-sm" data-testid="onset-shape">
          {t("Onset.detail.shape", {
            shape: nf.format(r.weibull_shape!),
            low: nf.format(r.weibull_shape_ci_low!),
            high: nf.format(r.weibull_shape_ci_high!),
            klass: t(`Onset.shapeClass.${r.weibull_shape_class}`),
          })}{" "}
          {t("Onset.detail.shapeCaveat")}
        </p>
      ) : (
        <p className="text-sm text-muted">{t("Onset.detail.noShape")}</p>
      )}
    </SummaryCard>
  );
}

function DateQuality({ r }: { r: OnsetRow }) {
  const t = useT();
  const locale = useLocale();
  const nf = new Intl.NumberFormat(locale);
  const reasons = REASONS.filter(
    (k) => (r.candidates_without_interval_by_reason[k] ?? 0) > 0,
  );
  return (
    <GroupedList
      header={t("Onset.detail.quality")}
      headingId="onset-quality"
      data-testid="onset-quality"
    >
      {showsMedian(r) ? null : (
        <Row data-testid="onset-quality-only">
          {t("Onset.detail.qualityOnly")}
        </Row>
      )}
      <Row>
        {t("Onset.detail.zeroDay", {
          n: nf.format(r.zero_day_reports),
          total: nf.format(r.reports_with_interval),
        })}
      </Row>
      <Row>
        {t("Onset.detail.dayOne", {
          n: nf.format(r.day_one_reports),
          total: nf.format(r.reports_with_interval),
        })}
      </Row>
      {r.reports_with_interval >= 2 ? (
        <Row>
          {t("Onset.detail.cluster", {
            n: nf.format(r.largest_date_cluster),
          })}
        </Row>
      ) : null}
      {r.event_year_min !== null && r.event_year_max !== null ? (
        <Row>
          {t("Onset.detail.years", {
            from: String(r.event_year_min),
            to: String(r.event_year_max),
          })}
        </Row>
      ) : null}
      {reasons.length ? (
        <Row>
          <span>{t("Onset.detail.withoutInterval")}</span>
          <ul className="list-disc ps-5 text-sm">
            {reasons.map((k) => (
              <li key={k}>
                {t(`Onset.reason.${k}`)}:{" "}
                <span className="mono">
                  {nf.format(r.candidates_without_interval_by_reason[k] ?? 0)}
                </span>
              </li>
            ))}
          </ul>
        </Row>
      ) : null}
    </GroupedList>
  );
}

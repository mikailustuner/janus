"use client";
/**
 * The FAERS onset table page (research-tools Req 2; faers-onset-table design §7): the 65 PIPC
 * rows in one sortable table (count and status first, a median with its exact interval only for
 * `described` and `small_sample` rows), the framing that keeps the numbers honest (descriptive,
 * not causal, not incidence; reports, not people), the caveats, a status legend and downloads.
 * Each row opens its detail page. Demo mode answers from the recorded file with no request.
 */
import { useLocale } from "next-intl";
import { useMemo, useState } from "react";

import {
  BackLink,
  Disclosure,
  GroupedList,
  LargeTitle,
  Row,
} from "@/components/cards";
import { ChevronIcon, DownloadIcon } from "@/components/icons";
import { StateView } from "@/components/StateView";
import { useCall } from "@/flow/useCall";
import { Link } from "@/i18n/navigation";
import {
  CAVEATS,
  demoOnset,
  liveOnset,
  loadOnsetFixture,
  ONSET_STATUSES,
  showsMedian,
  sortRows,
  type OnsetClient,
  type OnsetRow,
  type OnsetTable as Table,
  type SortDir,
  type SortKey,
} from "@/research/onset";
import { useT, type Translate } from "@/theme/words";
import { useVocabulary } from "@/vocabulary/use";
import type { Loaded } from "@/vocabulary";

import { useDemoClient } from "./useDemoClient";

const REPO = "https://github.com/mikailustuner/janus/blob/main";
const EXTERNAL = { target: "_blank", rel: "noopener noreferrer" } as const;

export function useOnsetClient() {
  return useDemoClient(liveOnset, loadOnsetFixture, demoOnset);
}

/** "Drug A → event → drug B" in the interface language, the PIPC English text as fallback. */
export function patternTitle(
  t: Translate,
  v: Loaded | null,
  r: Pick<
    OnsetRow,
    "pipc_position" | "pipc_drug_a" | "pipc_adverse_event" | "pipc_drug_b"
  >,
): string {
  const row = v?.vocab.cascades[String(r.pipc_position)];
  return t("Onset.pattern", {
    drugA: row?.drug_a ?? r.pipc_drug_a,
    event: row?.adverse_event ?? r.pipc_adverse_event,
    drugB: row?.drug_b ?? r.pipc_drug_b,
  });
}

/** The labels every onset screen carries (medical-safety rule 6; faers-onset-table Req 4). */
export function OnsetFraming({ recorded }: { recorded: string | null }) {
  const t = useT();
  return (
    <div className="flex flex-col gap-2">
      <p className="card p-4 font-bold" data-testid="onset-framing">
        {t("Onset.framing")}
      </p>
      <p className="text-sm text-muted" role="note" data-testid="onset-review">
        {t("Onset.review")}
      </p>
      {recorded ? (
        <p className="chip self-start" data-testid="onset-demo">
          {t("Onset.demo", { date: recorded })}
        </p>
      ) : null}
    </div>
  );
}

export function Caveats({ caveats }: { caveats: Record<string, string> }) {
  const t = useT();
  return (
    <GroupedList
      header={t("Onset.caveats.title")}
      headingId="onset-caveats"
      data-testid="onset-caveats"
      footer={
        <Disclosure summary={t("Onset.caveats.english")}>
          <ul className="flex flex-col gap-2" lang="en">
            {Object.entries(caveats).map(([k, v]) => (
              <li key={k} className="text-sm break-words">
                {v}
              </li>
            ))}
          </ul>
        </Disclosure>
      }
    >
      {CAVEATS.map((c) => (
        <Row key={c}>{t(`Onset.caveats.${c}`)}</Row>
      ))}
    </GroupedList>
  );
}

export function OnsetTable() {
  const t = useT();
  const { client, recorded, failed } = useOnsetClient();
  const call = useCall(client ? () => client.table() : null, [client]);
  return (
    <>
      <BackLink href="/research">{t("Research.title")}</BackLink>
      <LargeTitle
        title={t("Onset.title")}
        summary={
          call.status === "ok"
            ? t("Onset.summary", {
                rows: call.data.summary.rows,
                medians: call.data.summary.rows_with_median,
              })
            : undefined
        }
        summaryTestId="onset-summary"
      />
      <p className="max-w-[72ch]">{t("Onset.intro")}</p>
      <OnsetFraming recorded={recorded} />
      {failed ? (
        <StateView state="error" messageKey="Errors.generic" />
      ) : call.status === "error" ? (
        <StateView
          state="error"
          messageKey={call.error.messageKey}
          retry={call.retry}
        />
      ) : call.status !== "ok" || !client ? (
        <StateView state="loading" label={t("Onset.loading")} />
      ) : (
        <Body table={call.data} client={client} />
      )}
    </>
  );
}

function Body({ table, client }: { table: Table; client: OnsetClient }) {
  const t = useT();
  const locale = useLocale();
  const snapshot = new Intl.DateTimeFormat(locale, {
    dateStyle: "long",
    timeZone: "UTC",
  }).format(new Date(`${table.faers_snapshot_date}T00:00:00Z`));
  return (
    <>
      <RowsTable rows={table.rows} />
      <div className="grid gap-group lg:grid-cols-2 lg:items-start">
        <div className="flex min-w-0 flex-col gap-group">
          <Caveats caveats={table.caveats} />
        </div>
        <div className="flex min-w-0 flex-col gap-group">
          <GroupedList
            header={t("Onset.statusLegend.title")}
            headingId="onset-legend"
            data-testid="onset-legend"
          >
            {ONSET_STATUSES.map((s) => (
              <Row key={s}>
                <span className="font-bold">{t(`Onset.status.${s}`)}</span>
                <span className="text-sm text-muted">
                  {t(`Onset.statusLegend.${s}`)}
                </span>
              </Row>
            ))}
          </GroupedList>
          <GroupedList
            header={t("Onset.files.title")}
            headingId="onset-files"
            data-testid="onset-files"
            footer={
              <>
                <p className="mono break-all">
                  {t("Onset.files.version", { version: table.version })}
                </p>
                <p>
                  {t("Onset.files.window", {
                    quarters: table.faers_receipt_quarters.join(", "),
                    date: snapshot,
                  })}
                </p>
                <p>{t("Onset.files.licence")}</p>
                <p className="break-words" lang="en">
                  {table.attribution}
                </p>
                <p className="break-words" lang="en">
                  {table.meddra_notice}
                </p>
              </>
            }
          >
            {(["csv", "json"] as const).map((kind) => (
              <li key={kind} className="row-link">
                <a
                  href={client.download(kind)}
                  download={`janus-faers-onset-pipc.${kind}`}
                  data-testid={`onset-download-${kind}`}
                >
                  <DownloadIcon size={18} className="shrink-0" />
                  <span className="min-w-0 flex-1">
                    {t(`Onset.files.${kind}`)}
                  </span>
                </a>
              </li>
            ))}
            <li className="row-link">
              <a href={`${REPO}/docs/open-data.md`} {...EXTERNAL}>
                <span className="min-w-0 flex-1">
                  {t("Onset.files.dictionary")}
                </span>
              </a>
            </li>
          </GroupedList>
        </div>
      </div>
    </>
  );
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "position", label: "Onset.cols.row" },
  { key: "reports", label: "Onset.cols.reports" },
  { key: "interval", label: "Onset.cols.interval" },
  { key: "median", label: "Onset.cols.median" },
  { key: "status", label: "Onset.cols.status" },
];

function RowsTable({ rows }: { rows: readonly OnsetRow[] }) {
  const t = useT();
  const vocab = useVocabulary();
  const locale = useLocale();
  const nf = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({
    key: "position",
    dir: "ascending",
  });
  const sorted = useMemo(
    () => sortRows(rows, sort.key, sort.dir),
    [rows, sort],
  );
  const toggle = (key: SortKey) =>
    setSort((s) =>
      s.key === key
        ? {
            key,
            dir: s.dir === "ascending" ? "descending" : "ascending",
          }
        : { key, dir: key === "position" ? "ascending" : "descending" },
    );
  const head = (key: SortKey, label: string) => (
    <th
      key={key}
      scope="col"
      aria-sort={sort.key === key ? sort.dir : undefined}
    >
      <button
        type="button"
        className="-mx-1 inline-flex min-h-11 min-w-11 items-center gap-1 whitespace-nowrap rounded-[var(--radius-segment)] px-1 text-start font-bold hover:bg-chip"
        onClick={() => toggle(key)}
        data-testid={`onset-sort-${key}`}
      >
        {t(label)}
        <ChevronIcon
          size={14}
          className={`shrink-0 transition-transform duration-150 ${sort.key !== key ? "opacity-30" : ""} ${sort.key === key && sort.dir === "ascending" ? "-rotate-90" : "rotate-90"}`}
        />
      </button>
    </th>
  );
  return (
    <section
      className="flex min-w-0 flex-col gap-2"
      aria-labelledby="onset-table"
    >
      <h2 id="onset-table" className="group-header">
        {t("Onset.tableTitle")}
      </h2>
      <p className="text-sm text-muted">{t("Onset.tableHint")}</p>
      <div
        className="card relative overflow-x-auto p-0"
        tabIndex={0}
        role="region"
        aria-label={t("Onset.tableTitle")}
      >
        <table className="tm-table" data-testid="onset-rows">
          <caption className="sr-only">
            {t("Onset.caption", {
              key: t(COLUMNS.find((c) => c.key === sort.key)!.label),
              dir: t(`Onset.sort.${sort.dir}`),
            })}
          </caption>
          <thead>
            <tr>
              {head("position", "Onset.cols.row")}
              <th scope="col" className="min-w-[14rem] max-w-[24rem]">
                {t("Onset.cols.pattern")}
              </th>
              {COLUMNS.slice(1).map((c) => head(c.key, c.label))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => {
              const stats = showsMedian(r);
              return (
                <tr
                  key={r.pipc_position}
                  data-testid="onset-row"
                  data-status={r.status}
                >
                  <th scope="row" className="mono">
                    {r.pipc_position}
                  </th>
                  <td>
                    <Link
                      href={{
                        pathname: "/research/faers-onset/row",
                        hash: String(r.pipc_position),
                      }}
                      className="inline-flex min-h-11 items-center font-bold break-words"
                    >
                      {patternTitle(t, vocab, r)}
                    </Link>
                  </td>
                  <td className="mono whitespace-nowrap">
                    {nf.format(r.candidate_reports)}
                  </td>
                  <td className="mono whitespace-nowrap">
                    {nf.format(r.reports_with_interval)}
                  </td>
                  <td className="mono whitespace-nowrap">
                    {stats ? (
                      <>
                        {t("Onset.days", { n: nf.format(r.median_days!) })}
                        <span className="block text-muted">
                          {t("Onset.ci", {
                            low: nf.format(r.median_exact_ci_low_days!),
                            high: nf.format(r.median_exact_ci_high_days!),
                          })}
                        </span>
                        {r.median_reflects_zero_heaping ? (
                          <span
                            className="block font-body font-bold"
                            data-testid="onset-heaping-flag"
                          >
                            {t("Onset.heapingShort")}
                          </span>
                        ) : null}
                      </>
                    ) : (
                      <>
                        <span aria-hidden>—</span>
                        <span className="sr-only">{t("Onset.noMedian")}</span>
                      </>
                    )}
                  </td>
                  <td>
                    <span className="whitespace-nowrap">
                      {t(`Onset.status.${r.status}`)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

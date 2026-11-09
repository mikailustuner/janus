/**
 * The FAERS time-to-onset table for the 65 PIPC rows (faers-onset-table design §7;
 * research-tools Req 2): decoder, clients and the pure view model. Live: GET only. Demo: the
 * answer recorded from the real local API (`faers-onset.recorded.json`), no request at all.
 *
 * Presentation rules of design §7 live here, not in the components: the count and the status
 * come first; a median (with its exact interval and quartiles) is shown only for `described` and
 * `small_sample` rows; a `count_only` or `cluster_dominated` row never shows a statistic.
 */
import { HttpClient, type Result } from "@/api/client";
import * as D from "@/api/decode";

export const ONSET_STATUSES = [
  "described",
  "small_sample",
  "cluster_dominated",
  "count_only",
  "no_interval",
  "no_candidate_reports",
] as const;
export type OnsetStatus = (typeof ONSET_STATUSES)[number];

const n = D.nullable(D.num);
const i = D.nullable(D.int);

export const onsetRow = D.obj({
  pipc_position: D.int,
  pipc_system: D.str,
  pipc_drug_a: D.str,
  pipc_adverse_event: D.str,
  pipc_drug_b: D.str,
  pipc_locator: D.str,
  index_class: D.str,
  event_key: D.str,
  event_pts: D.arr(D.str),
  shared_with_positions: D.arr(D.int),
  route_groups_counted: D.arr(D.str),
  candidate_reports: D.int,
  reports_with_interval: D.int,
  usable_share: n,
  candidates_without_interval_by_reason: D.record(D.int),
  distinct_intervals: D.int,
  event_year_min: i,
  event_year_max: i,
  status: D.lit(...ONSET_STATUSES),
  small_sample: D.bool,
  omitted_reason: D.nullable(D.str),
  median_days: n,
  q25_days: n,
  q75_days: n,
  median_exact_ci_low_days: n,
  median_exact_ci_high_days: n,
  median_exact_ci_coverage: n,
  median_reflects_zero_heaping: D.nullable(D.bool),
  median_days_without_day_one: n,
  reports_without_day_one: D.int,
  median_days_earliest_class_start: n,
  median_days_distinct_date_pairs: n,
  sensitivity_omitted_reason: D.nullable(D.str),
  zero_day_reports: D.int,
  zero_day_share: n,
  day_one_reports: D.int,
  day_one_share: n,
  largest_date_cluster: D.int,
  weibull_shape: n,
  weibull_shape_ci_low: n,
  weibull_shape_ci_high: n,
  weibull_shape_class: D.nullable(D.lit("early", "random", "wear_out")),
  shape_omitted_reason: D.nullable(D.str),
  row_notes: D.arr(D.obj({ code: D.str, note: D.str })),
  descriptive_only: D.lit(true),
  causal: D.lit(false),
  incidence: D.lit(false),
  counts_are: D.lit("reports"),
});

export const onsetTable = D.obj({
  dataset: D.lit("janus-faers-onset-pipc"),
  version: D.str,
  built_at: D.str,
  faers_receipt_quarters: D.arr(D.str),
  faers_snapshot_date: D.str,
  license: D.lit("CC BY 4.0"),
  attribution: D.str,
  meddra_notice: D.str,
  review_status: D.str,
  descriptive_only: D.lit(true),
  causal: D.lit(false),
  incidence: D.lit(false),
  counts_are: D.lit("reports"),
  caveats: D.record(D.str),
  summary: D.obj({
    rows: D.int,
    rows_with_median: D.int,
    by_status: D.record(D.int),
  }),
  rows: D.arr(onsetRow, 1),
});

export const onsetRowOut = D.obj({
  dataset: D.lit("janus-faers-onset-pipc"),
  version: D.str,
  faers_receipt_quarters: D.arr(D.str),
  license: D.lit("CC BY 4.0"),
  attribution: D.str,
  meddra_notice: D.str,
  caveats: D.record(D.str),
  row: onsetRow,
});

export type OnsetRow = D.Infer<typeof onsetRow>;
export type OnsetTable = D.Infer<typeof onsetTable>;
export type OnsetRowOut = D.Infer<typeof onsetRowOut>;

export interface OnsetFixture {
  recorded: string;
  table: unknown;
  csv: string;
}

export interface OnsetClient {
  table(): Promise<Result<OnsetTable>>;
  row(position: number): Promise<Result<OnsetRowOut>>;
  download(kind: "json" | "csv"): string;
}

export const POSITION = /^[1-9]\d?$/;

const http = new HttpClient();

export const liveOnset: OnsetClient = {
  table: () => http.call("open/faers-onset", "GET", null, onsetTable),
  row: async (p) =>
    POSITION.test(String(p))
      ? http.call(
          "open/faers-onset/row",
          "GET",
          null,
          onsetRowOut,
          undefined,
          `open/faers-onset/${p}`,
        )
      : {
          ok: false,
          error: {
            kind: "build",
            route: "open/faers-onset/row",
            messageKey: "Errors.client_defect",
          },
        },
  download: (kind) =>
    kind === "json" ? "/api/open/faers-onset" : "/api/open/faers-onset.csv",
};

export function demoOnset(fx: OnsetFixture): OnsetClient {
  const decoded = D.decode(onsetTable, fx.table);
  const contract = (route: "open/faers-onset" | "open/faers-onset/row") =>
    ({
      ok: false,
      error: { kind: "contract", route, messageKey: "Errors.generic" },
    }) as const;
  return {
    table: async () =>
      decoded.ok
        ? { ok: true, data: decoded.value }
        : contract("open/faers-onset"),
    row: async (p) => {
      if (!decoded.ok) return contract("open/faers-onset/row");
      const t = decoded.value;
      const row = t.rows.find((r) => r.pipc_position === p);
      if (!row)
        return {
          ok: false,
          error: {
            kind: "http",
            route: "open/faers-onset/row",
            status: 404,
            code: "unknown_position",
            fields: [],
            messageKey: "Onset.errors.unknown",
          },
        };
      return {
        ok: true,
        data: {
          dataset: t.dataset,
          version: t.version,
          faers_receipt_quarters: t.faers_receipt_quarters,
          license: t.license,
          attribution: t.attribution,
          meddra_notice: t.meddra_notice,
          caveats: t.caveats,
          row,
        },
      };
    },
    download: (kind) =>
      kind === "json"
        ? `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(fx.table, null, 1))}`
        : `data:text/csv;charset=utf-8,${encodeURIComponent(fx.csv)}`,
  };
}

export function loadOnsetFixture(): Promise<OnsetFixture> {
  return import("./faers-onset.recorded.json").then(
    (m) => m.default as unknown as OnsetFixture,
  );
}

// --- view model ----------------------------------------------------------------------------------

/** A median (and its interval, quartiles, sensitivities) may be shown for these statuses only. */
export function showsStatistics(row: Pick<OnsetRow, "status">): boolean {
  return row.status === "described" || row.status === "small_sample";
}

/**
 * A median is shown only with both bounds of its exact 95 % interval (medical-safety rule 6), and
 * only for rows that may show statistics.
 */
export function showsMedian(row: OnsetRow): boolean {
  return (
    showsStatistics(row) &&
    row.median_days !== null &&
    row.median_exact_ci_low_days !== null &&
    row.median_exact_ci_high_days !== null
  );
}

/** The Weibull shape is shown only where the build published it (described rows). */
export function showsShape(row: OnsetRow): boolean {
  return (
    row.status === "described" &&
    row.weibull_shape !== null &&
    row.weibull_shape_ci_low !== null &&
    row.weibull_shape_ci_high !== null
  );
}

export type SortKey = "position" | "reports" | "interval" | "median" | "status";
export type SortDir = "ascending" | "descending";

/** Sort value of a row; a row without a shown median sorts after every row with one. */
function value(r: OnsetRow, key: SortKey): number {
  switch (key) {
    case "position":
      return r.pipc_position;
    case "reports":
      return r.candidate_reports;
    case "interval":
      return r.reports_with_interval;
    case "status":
      return ONSET_STATUSES.indexOf(r.status);
    case "median":
      // A median that only shows same-day heaping is not comparable (statistician review).
      return showsMedian(r) && !r.median_reflects_zero_heaping
        ? r.median_days!
        : Number.NaN;
  }
}

/**
 * Rows in the chosen order; ties keep the PIPC order. For the median, rows without a shown median
 * stay at the end in both directions (they have no number to compare).
 */
export function sortRows(
  rows: readonly OnsetRow[],
  key: SortKey,
  dir: SortDir,
): OnsetRow[] {
  const sign = dir === "ascending" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = value(a, key);
    const vb = value(b, key);
    const na = Number.isNaN(va);
    const nb = Number.isNaN(vb);
    if (na || nb)
      return na && nb ? a.pipc_position - b.pipc_position : na ? 1 : -1;
    return sign * (va - vb) || a.pipc_position - b.pipc_position;
  });
}

/**
 * The caveats the table and every row view show, in reading order: every key of the dataset's
 * `caveats` (faers-onset-table Req 4.2) has a translated short form in the messages; the
 * dataset's English text is in a disclosure. A test keeps this list equal to the dataset's keys.
 */
export const CAVEATS = [
  "descriptive",
  "not_incidence",
  "selection",
  "event_date_report_level",
  "zero_day",
  "day_one",
  "clusters",
  "small_sample",
  "median_interval",
  "shortest_interval",
  "shared_rows",
  "class_membership",
  "receipt_window",
  "weibull",
] as const;

/**
 * The weekly data-quality report (data-quality design §9; research-tools Req 1): decoder, clients
 * and the pure view model. Live: GET only through the experience HTTP client. Demo: the answer
 * recorded from the real local API (`data-quality.recorded.json`, scripts/record-research.mjs),
 * with no request at all.
 *
 * The report carries codes, counts and English Wikidata labels only (data-quality Req 4.2): no
 * TİTCK row, product name or barcode exists in it, and the decoder keeps only the fields the
 * screen shows, so nothing else could reach the page by accident.
 */
import { HttpClient, type Result } from "@/api/client";
import * as D from "@/api/decode";

export const CLASSES = [
  "confirmed_error",
  "needs_pharmacist",
  "benign_difference",
] as const;
export const STATUSES = ["new", "persisting", "resolved"] as const;
export const CHECKS = [
  "exclusion_status",
  "item_group",
  "regulator_group",
  "substance_code_keys",
] as const;
export type Klass = (typeof CLASSES)[number];
export type Status = (typeof STATUSES)[number];

const klass = D.lit(...CLASSES);
const status = D.lit(...STATUSES);
const check = D.lit(...CHECKS);

export const finding = D.obj({
  id: D.str,
  status,
  class: klass,
  class_changed_from: D.nullable(klass),
  check,
  source: D.str,
  key: D.str,
  label_en: D.nullable(D.str),
  wikidata_url: D.nullable(D.str),
  code: D.str,
  compared_codes: D.arr(D.str),
  products: D.int,
  reasons: D.arr(D.str),
  other_keys: D.arr(D.str),
  upstream: D.nullable(D.lit("persisting", "resolved_upstream")),
  whocc_group_urls: D.arr(D.str),
  how_to_find: D.str,
});

export const dataQualityReport = D.obj({
  dataset: D.lit("janus-data-quality"),
  version: D.str,
  run_id: D.str,
  run_date: D.pattern(/^\d{4}-\d{2}-\d{2}$/),
  previous_run_id: D.nullable(D.str),
  previous_version: D.nullable(D.str),
  license: D.lit("CC BY 4.0"),
  license_url: D.str,
  attribution: D.str,
  review_status: D.str,
  notices: D.arr(D.str),
  resolution_dataset: D.str,
  sources: D.record(
    D.obj({
      pipeline: D.str,
      run_id: D.str,
      snapshot_date: D.str,
      license: D.str,
    }),
  ),
  summary: D.obj({
    findings: D.int,
    by_class: D.obj({
      confirmed_error: D.int,
      needs_pharmacist: D.int,
      benign_difference: D.int,
    }),
    by_status: D.obj({ new: D.int, persisting: D.int, resolved: D.int }),
    confirmed_errors_still_published: D.int,
    confirmed_errors_resolved_upstream: D.int,
  }),
  findings: D.arr(finding),
});

export type Finding = D.Infer<typeof finding>;
export type DataQualityReport = D.Infer<typeof dataQualityReport>;

export interface DataQualityFixture {
  recorded: string;
  report: unknown;
  csv: string;
  md: string;
}

export type DownloadKind = "json" | "csv" | "md";

export interface DataQualityClient {
  report(): Promise<Result<DataQualityReport>>;
  /** A download address: the API file live, a `data:` URL of the recorded file in demo mode. */
  download(kind: DownloadKind): string;
}

const http = new HttpClient();

export const liveDataQuality: DataQualityClient = {
  report: () => http.call("open/data-quality", "GET", null, dataQualityReport),
  download: (kind) =>
    kind === "json"
      ? "/api/open/data-quality"
      : `/api/open/data-quality.${kind}`,
};

export function demoDataQuality(fx: DataQualityFixture): DataQualityClient {
  return {
    report: async () => {
      const r = D.decode(dataQualityReport, fx.report);
      return r.ok
        ? { ok: true, data: r.value }
        : {
            ok: false,
            error: {
              kind: "contract",
              route: "open/data-quality",
              messageKey: "Errors.generic",
            },
          };
    },
    download: (kind) =>
      kind === "json"
        ? `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(fx.report, null, 1))}`
        : kind === "csv"
          ? `data:text/csv;charset=utf-8,${encodeURIComponent(fx.csv)}`
          : `data:text/markdown;charset=utf-8,${encodeURIComponent(fx.md)}`,
  };
}

export function loadDataQualityFixture(): Promise<DataQualityFixture> {
  return import("./data-quality.recorded.json").then(
    (m) => m.default as unknown as DataQualityFixture,
  );
}

// --- view model ----------------------------------------------------------------------------------

/** Findings per class and status (new, persisting, resolved), every cell present. */
export function classStatusCounts(
  findings: readonly Finding[],
): Record<Klass, Record<Status, number>> {
  const out = Object.fromEntries(
    CLASSES.map((c) => [c, Object.fromEntries(STATUSES.map((s) => [s, 0]))]),
  ) as Record<Klass, Record<Status, number>>;
  for (const f of findings) out[f.class][f.status] += 1;
  return out;
}

export interface Filter {
  klass: Klass | "all";
  status: Status | "all";
  query: string;
}

const fold = (s: string) =>
  s.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().trim();

/**
 * The findings a filter keeps, in a stable order: class (confirmed, needs pharmacist, benign),
 * then status (new, persisting, resolved), then label and id. The query matches the English
 * label, the key and the codes, ignoring case and accents.
 */
export function filterFindings(
  findings: readonly Finding[],
  f: Filter,
): Finding[] {
  const q = fold(f.query);
  return findings
    .filter(
      (x) =>
        (f.klass === "all" || x.class === f.klass) &&
        (f.status === "all" || x.status === f.status) &&
        (!q ||
          [x.label_en ?? "", x.key, x.code, ...x.compared_codes].some((s) =>
            fold(s).includes(q),
          )),
    )
    .sort(
      (a, b) =>
        CLASSES.indexOf(a.class) - CLASSES.indexOf(b.class) ||
        STATUSES.indexOf(a.status) - STATUSES.indexOf(b.status) ||
        (a.label_en ?? a.key).localeCompare(b.label_en ?? b.key, "en") ||
        a.id.localeCompare(b.id, "en"),
    );
}

/** Evidence addresses are shown as links only on the two hosts the report uses (DP-R3). */
const EVIDENCE_HOSTS = ["www.wikidata.org", "atcddd.fhi.no"];

export function evidenceLink(url: string | null): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "https:" && EVIDENCE_HOSTS.includes(u.hostname)
      ? u.href
      : null;
  } catch {
    return null;
  }
}

/** The level-4 group of a WHOCC group page address (`?code=R06AE`), for the link text. */
export function whoccGroup(url: string): string | null {
  try {
    const code = new URL(url).searchParams.get("code");
    return code && /^[A-Z]\d{2}[A-Z]{2}$/.test(code) ? code : null;
  } catch {
    return null;
  }
}

/** Where the finding can be reported upstream (the source that publishes the code). */
export function upstreamTarget(
  f: Finding,
): "wikidata" | "titck" | "cima" | "titck_cima" | "bdpm" {
  if (f.source === "wikidata") return "wikidata";
  if (f.source === "titck") return "titck";
  if (f.source === "eu_es_cima") return "cima";
  if (f.source === "eu_fr_bdpm") return "bdpm";
  return "titck_cima";
}

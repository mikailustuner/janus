/**
 * Pure view logic of the researcher screens (light-face design §10): names in the reader's
 * language, tied-rank text parts, the CSV of the export, and the per-case summary. No I/O.
 */
import type { CaseRun, ExportRow, Rank } from "./model";

export type Labels = Record<string, string>;

/** The name in the reader's language, else English, else the first one, else the key. */
export function nameIn(labels: Labels, locale: string, key = ""): string {
  return (
    labels[locale] ?? labels.en ?? Object.values(labels)[0] ?? key
  ).trim();
}

export interface RankText {
  key: "Light.card.rank" | "Light.card.rankTied";
  values: { best: number; worst: number; population: number };
}

/** Tied ranks are a range, never a single position (design §6). */
export function rankText(rank: Rank): RankText {
  return {
    key: rank.best === rank.worst ? "Light.card.rank" : "Light.card.rankTied",
    values: { best: rank.best, worst: rank.worst, population: rank.population },
  };
}

export function caseRank(run: CaseRun): RankText | null {
  return run.rank ? rankText(run.rank) : null;
}

export const CSV_COLUMNS = [
  "goal",
  "ingredient",
  "ingredient_name_en",
  "rank_best",
  "rank_worst",
  "population",
  "signal_types",
  "label_regions",
  "labels_with_effect",
  "labels_total",
  "label_terms",
  "faers_reports",
  "faers_ror",
  "faers_ror_low",
  "faers_ror_high",
  "patient_reported_released",
  "source_ids",
] as const satisfies readonly (keyof ExportRow)[];

function cell(v: unknown): string {
  const text =
    v === null || v === undefined
      ? ""
      : Array.isArray(v)
        ? v.join("|")
        : String(v);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** RFC 4180 CSV: comma, CRLF, quotes doubled; lists joined with `|`. */
export function toCsv(rows: readonly ExportRow[]): string {
  const lines = [CSV_COLUMNS.join(",")];
  for (const r of rows) lines.push(CSV_COLUMNS.map((c) => cell(r[c])).join(","));
  return lines.join("\r\n") + "\r\n";
}

/** The inverse of `toCsv` for the text cells (tests and re-import). */
export function parseCsv(text: string): string[][] {
  const out: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]!;
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\r" && text[i + 1] === "\n") {
      row.push(field);
      out.push(row);
      row = [];
      field = "";
      i++;
    } else field += ch;
  }
  if (field || row.length) {
    row.push(field);
    out.push(row);
  }
  return out;
}

/** The informative-hit summary of a run, as message values. */
export function summaryValues(
  s: { informative_hits: number; expected_hits_by_chance: number },
  cases: number,
  k: number,
  locale: string,
): Record<string, string | number> {
  return {
    informative: s.informative_hits,
    cases,
    k,
    chance: new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(
      s.expected_hits_by_chance,
    ),
  };
}

export function fileName(build: string, ext: "json" | "csv"): string {
  const safe = build.replace(/[^A-Za-z0-9-]/g, "");
  return `janus-light-${safe}-cc-by-4.0.${ext}`;
}

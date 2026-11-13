/**
 * Downloads and citation of the validation studies (plan D3.2). Each card's numbers as one CSV
 * (RFC 4180, comma separated, dot decimals and no locale formatting, so any tool reads it), from
 * the same generated file the cards show; and the citation of the release, from CITATION.cff.
 */
import { VALIDATION, type CardKey } from "./validation";

export const CSV_COLUMNS = [
  "study",
  "measure",
  "k",
  "n",
  "estimate",
  "ci95_low",
  "ci95_high",
  "cluster_lower",
  "threshold",
  "met",
] as const;

export type CsvRow = Partial<
  Record<(typeof CSV_COLUMNS)[number], string | number | boolean | null>
>;

type Prop = {
  k: number;
  n: number;
  estimate: number;
  low: number;
  high: number;
};

function prop(study: CardKey, measure: string, m: Prop): CsvRow {
  return {
    study,
    measure,
    k: m.k,
    n: m.n,
    estimate: m.estimate,
    ci95_low: m.low,
    ci95_high: m.high,
  };
}

/** The rows of one card: every number the card shows, with its interval and threshold. */
export function studyRows(card: CardKey): CsvRow[] {
  switch (card) {
    case "cascade": {
      const c = VALIDATION.cascade;
      return [
        {
          ...prop(card, "specificity_pairs", c.specificity),
          threshold: c.specificity.bound,
          met: c.specificity.met,
        },
        {
          ...prop(card, "sensitivity_pairs", c.sensitivity),
          threshold: c.sensitivity.bound,
          met: c.sensitivity.met,
        },
        {
          study: card,
          measure: "within_rule_base_scope",
          k: c.inScope.k,
          n: c.inScope.n,
          estimate: c.inScope.k / c.inScope.n,
        },
        prop(card, "comparison_alert_rate", c.comparisonAlert),
      ];
    }
    case "faers": {
      const f = VALIDATION.faers;
      return [
        {
          study: card,
          measure: "auc_ln_ror",
          n: f.auc.nPositive + f.auc.nNegative,
          estimate: f.auc.estimate,
          ci95_low: f.auc.low,
          ci95_high: f.auc.high,
          threshold: f.auc.bound,
          met: f.auc.met,
        },
        prop(card, "negatives_ci_excluding_1_nominal", f.negativesNominal),
        prop(card, "negatives_p_below_005_calibrated", f.negativesCalibrated),
        prop(card, "evans_sensitivity", f.evansSensitivity),
        prop(card, "evans_specificity", f.evansSpecificity),
      ];
    }
    case "modelkitPrecision": {
      const p = VALIDATION.modelkitPrecision;
      return [
        ...p.sources.map((s) => ({
          study: card,
          measure: `precision:${s.key}:level_${s.level}`,
          n: s.values,
          estimate: s.precision,
          ci95_low: s.wilsonLow,
          ci95_high: s.wilsonHigh,
          cluster_lower: s.clusterLower,
          threshold: p.bound,
          met: s.met,
        })),
        ...p.curve.map((c) => ({
          study: card,
          measure: `clinicaltrials_gov:level_at_least_${c.level}:coverage_${c.coverage}`,
          estimate: c.precision,
          cluster_lower: c.clusterLower,
          threshold: p.bound,
          met: c.met,
        })),
      ];
    }
    case "modelkitGate": {
      const g = VALIDATION.modelkitGate;
      return [
        {
          study: card,
          measure: "drugs_with_auc_and_cmax_tested",
          k: g.both,
          threshold: g.needed,
          met: g.interpretable,
        },
        {
          study: card,
          measure: "values_read_correctly",
          k: g.read.k,
          n: g.read.n,
          estimate: g.read.k / g.read.n,
          ci95_low: g.read.low,
          ci95_high: g.read.high,
          cluster_lower: g.read.clusterLower,
        },
        {
          study: card,
          measure: `auc_within_2_fold:${g.auc.drugs}_drugs`,
          k: g.auc.k,
          n: g.auc.n,
          estimate: g.auc.k / g.auc.n,
          ci95_low: g.auc.low,
          ci95_high: g.auc.high,
        },
        ...g.rows.map((r) => ({
          study: card,
          measure: `claim:${r.id}:${r.status}`,
        })),
      ];
    }
  }
}

function cell(v: CsvRow[keyof CsvRow]): string {
  if (v === undefined || v === null) return "";
  const s = String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** RFC 4180 text with a header row and CRLF line ends. */
export function toCsv(rows: CsvRow[]): string {
  const lines = [
    CSV_COLUMNS.join(","),
    ...rows.map((r) => CSV_COLUMNS.map((c) => cell(r[c])).join(",")),
  ];
  return `${lines.join("\r\n")}\r\n`;
}

export function csvFileName(card: CardKey): string {
  return `janus-${card}-v${VALIDATION.citation.version}.csv`;
}

/** The citation of this release: author, title, version, year, DOI when there is one, else URL. */
export function citationText(): string {
  const c = VALIDATION.citation;
  const year = c.date.slice(0, 4);
  const where = c.doi ? `https://doi.org/${c.doi}` : c.repository;
  return `${c.family} ${c.given.charAt(0)}. ${c.title}. Version ${c.version} [software]. ${year}. ${where}`;
}

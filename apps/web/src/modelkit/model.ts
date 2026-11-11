/**
 * The experimental drug model starter kit (model-kit Req 6): decoders for the read-only
 * `/modelkit/*` answers, the live client and a demo client over the recorded answers
 * (`modelkit.recorded.json`, no request at all), and the pure view model (hash key, status badge,
 * log-log chart maths, reason-code lookup). The API sends reason CODES; the interface translates
 * them (messages `ModelKit.reasons.*`). Research use only. Not for clinical decisions.
 */
import { HttpClient, type Result } from "@/api/client";
import * as D from "@/api/decode";

const n = D.nullable(D.num);

export const STATUSES = ["validated", "not_validated", "failed"] as const;
export type Status = (typeof STATUSES)[number];
export const TARGETS = ["janus", "mrgsolve", "pksim"] as const;
export type Target = (typeof TARGETS)[number];

const release = D.obj({
  run_id: D.str,
  snapshot_date: D.str,
  pipeline_version: D.str,
});
const statements = D.obj({
  research_use: D.str,
  expert_review: D.str,
  experimental: D.str,
});
const metric = D.obj({
  name: D.lit("auc", "cmax"),
  tested: D.bool,
  n_points: D.int,
  n_studies: D.int,
  gm_ratio: n,
  gmfe: n,
  within_2_fold_points: D.int,
  all_within_2_fold: D.nullable(D.bool),
});
const status = D.lit(...STATUSES);
const summary = D.obj({
  key: D.str,
  name: D.str,
  status,
  status_reasons: D.arr(D.str),
  has_set: D.bool,
  set_complete: D.bool,
  basis: D.nullable(D.str),
  rows: D.int,
  confirmed_rows: D.int,
  studies: D.int,
  auc: metric,
  cmax: metric,
  exportable: D.bool,
  experimental: D.lit(true),
});
const reasonOut = D.obj({ evidence_id: D.str, reason: D.str });
const point = D.obj({
  evidence_id: D.str,
  metric: D.lit("auc", "cmax"),
  study_id: D.str,
  dose_mg: D.num,
  observed: D.num,
  predicted: D.num,
  ratio: D.num,
  within_2_fold: D.bool,
});
const validation = D.obj({
  status,
  reasons: D.arr(D.str),
  metrics: D.arr(metric),
  points: D.arr(point),
  excluded: D.arr(reasonOut),
  suspect: D.arr(D.str),
  failed_point_ids: D.arr(D.str),
  interval_reason: D.str,
  interval_min_studies: D.int,
  interval_n_studies: D.int,
  band: D.arr(D.num),
  unit_note: D.str,
});
const interval = D.obj({
  metric: D.lit("auc", "cmax"),
  shown: D.bool,
  n_studies: D.int,
  min_studies: D.int,
  coverage: D.num,
  fold_half: n,
  reason: D.nullable(D.str),
});
const precision = D.obj({
  measured_on: D.str,
  n: D.int,
  correct: D.int,
  share: D.num,
  wilson_low: D.num,
  wilson_high: D.num,
  n_conservative: D.int,
  share_conservative: D.num,
  wilson_low_conservative: D.num,
  wilson_high_conservative: D.num,
  formulation_n: D.nullable(D.int),
  formulation_correct: D.nullable(D.int),
  formulation_share: n,
  formulation_wilson_low: n,
  formulation_wilson_high: n,
  target: D.num,
});
const param = D.obj({
  name: D.str,
  label: D.str,
  value: D.num,
  unit: D.str,
  confidence_class: D.lit("A", "B", "C"),
  n_studies: D.int,
  between_study_cv: n,
  derivation: D.nullable(D.str),
  notes: D.arr(D.str),
  evidence_ids: D.arr(D.str),
});
const paramSet = D.obj({
  model: D.str,
  model_reason: D.str,
  basis: D.lit("iv", "oral_apparent"),
  apparent: D.bool,
  complete: D.bool,
  missing: D.arr(D.str),
  warnings: D.arr(D.str),
  implied_half_life_h: n,
  stated_half_life_h: n,
  params: D.arr(param),
  left_out: D.arr(reasonOut),
  held_out_studies: D.arr(D.str),
});
const text = D.record(D.str);

export const SP_CLASSES = ["geriatric", "renal", "hepatic"] as const;
export const SP_GRADES = [
  "mild",
  "moderate",
  "severe",
  "esrd",
  "dialysis",
  "cp_a",
  "cp_b",
  "cp_c",
  "age65",
  "age75",
  "age80",
] as const;
const specialStatement = D.obj({
  pop_class: D.lit(...SP_CLASSES),
  grade: D.str,
  measure: D.lit("auc", "cmax"),
  ratio: D.num,
  ratio_text: D.str,
  definition: D.str,
  reference: D.str,
  quote: D.str,
  set_id: D.str,
  version: D.str,
  effective_date: D.str,
  section: D.str,
  n_labels: D.int,
  from_table: D.bool,
  source_url: D.str,
  status: D.lit("two_readers_agree"),
});
const specialAtlas = D.obj({
  measure: D.str,
  ratio: D.num,
  qualitative: D.bool,
  quote: D.str,
  set_id: D.str,
  version: D.str,
  n_labels: D.int,
  quote_checked: D.bool,
  source_url: D.str,
  status: D.lit("automated_extraction_unconfirmed"),
});
const specialOut = D.obj({
  statements: D.arr(specialStatement),
  atlas: D.arr(specialAtlas),
  notes: D.arr(D.str),
});
const specialPrecision = D.obj({
  measured_on: D.str,
  n: D.int,
  correct: D.int,
  share: D.num,
  wilson_low: D.num,
  wilson_high: D.num,
  n_conservative: D.int,
  share_conservative: D.num,
  wilson_low_conservative: D.num,
  wilson_high_conservative: D.num,
  target: D.num,
});
const specialSystem = D.obj({
  drugs: D.int,
  statements: D.int,
  by_class: D.record(D.int),
  drugs_by_class: D.record(D.int),
  atlas_drugs: D.int,
  atlas_rows: D.int,
  coverage: D.record(D.int),
  precision: D.nullable(specialPrecision),
});

export const drugsOut = D.obj({
  release,
  statements,
  drugs: D.arr(summary),
  total: D.int,
  offset: D.int,
  limit: D.int,
  counts: D.record(D.int),
});
export const drugOut = D.obj({
  release,
  statements,
  summary,
  parameter_set: D.nullable(paramSet),
  no_set_reasons: D.arr(D.str),
  validation,
  intervals: D.arr(interval),
  targets: D.arr(D.lit(...TARGETS)),
  special_populations: specialOut,
  reason_text: text,
});
const evidenceRow = D.obj({
  id: D.str,
  analyte: D.str,
  analyte_class: D.str,
  parameter: D.str,
  value: D.num,
  value_low: n,
  value_high: n,
  statistic: D.str,
  unit: D.str,
  value_si: D.num,
  dose: n,
  route: D.str,
  regimen: D.str,
  interval_h: n,
  population: D.nullable(D.str),
  n_subjects: D.nullable(D.int),
  formulation: D.str,
  coadministered: D.bool,
  study_id: D.str,
  source_id: D.str,
  source_locator: D.str,
  source_version: D.str,
  source_url: D.nullable(D.str),
  quote: D.str,
  reader_a: D.lit("agree", "disagree"),
  reader_b: D.lit("agree", "disagree"),
  confirmed: D.bool,
  confirm_reason: D.str,
  note: D.nullable(D.str),
  extracted_at: D.str,
  role: D.lit("building", "validation", "excluded"),
  reason: D.nullable(D.str),
  origin: D.str,
  derivation: D.nullable(D.str),
  arm_id: D.nullable(D.str),
  food: D.str,
  evidence_kind: D.str,
  dispersion_type: D.str,
  dispersion_low: n,
  dispersion_high: n,
});
export const evidenceOut = D.obj({
  release,
  statements,
  drug: D.str,
  rows: D.arr(evidenceRow),
  attribution: D.arr(D.str),
  reason_text: text,
});
export const systemOut = D.obj({
  release,
  statements,
  n_drugs: D.int,
  by_status: D.record(D.int),
  metrics: D.arr(
    D.obj({
      name: D.lit("auc", "cmax"),
      n_drugs: D.int,
      gmfe: n,
      within_2_fold: D.int,
      within_2_fold_share: n,
      wilson_low: n,
      wilson_high: n,
      n_points: D.int,
      points_within_2_fold: D.int,
      points_gmfe: n,
    }),
  ),
  n_studies: D.int,
  interpretable: D.bool,
  min_drugs_for_interpretation: D.int,
  n_drugs_both_tested: D.int,
  conformal: D.str,
  intervals: D.arr(interval),
  n_with_set: D.int,
  n_complete_set: D.int,
  rows_total: D.int,
  rows_confirmed: D.int,
  confirmed_parent_rows: D.int,
  formulation_counts: D.record(D.int),
  route_counts: D.record(D.int),
  not_validated_reasons: D.record(D.int),
  no_set_reasons: D.record(D.int),
  precision: D.nullable(precision),
  special_populations: specialSystem,
  missing: D.arr(D.str),
  caveats: D.arr(D.str),
  reason_text: text,
});

export type DrugSummary = D.Infer<typeof summary>;
export type DrugsOut = D.Infer<typeof drugsOut>;
export type DrugOut = D.Infer<typeof drugOut>;
export type ParamOut = D.Infer<typeof param>;
export type MetricOut = D.Infer<typeof metric>;
export type PointOut = D.Infer<typeof point>;
export type EvidenceRow = D.Infer<typeof evidenceRow>;
export type EvidenceOut = D.Infer<typeof evidenceOut>;
export type SystemOut = D.Infer<typeof systemOut>;
export type IntervalOut = D.Infer<typeof interval>;
export type SpecialStatement = D.Infer<typeof specialStatement>;
export type SpecialAtlas = D.Infer<typeof specialAtlas>;
export type SpecialOut = D.Infer<typeof specialOut>;
export type SpecialSystem = D.Infer<typeof specialSystem>;
export type PrecisionOut = D.Infer<typeof precision>;

export const FORMULATIONS = [
  "immediate_release",
  "solution",
  "modified_release",
  "fixed_dose_combination",
  "other_route",
  "unspecified",
] as const;
export const ROUTES = ["oral", "iv", "unknown"] as const;

export interface ModelKitFixture {
  recorded: string;
  drugs: unknown;
  validation: unknown;
  drug: Record<string, unknown>;
  evidence: Record<string, unknown>;
}

/** What the list page asks for: a name search, a status, only drugs with a set, one page. */
export interface DrugsQuery {
  q: string;
  status: Status | "";
  hasSet: boolean;
  offset: number;
  limit: number;
}
export const PAGE_SIZE = 25;
export const NO_QUERY: DrugsQuery = {
  q: "",
  status: "",
  hasSet: false,
  offset: 0,
  limit: PAGE_SIZE,
};

/** The query string of the live list route (only what differs from the defaults). */
export function drugsPath(query: DrugsQuery): string {
  const p = new URLSearchParams();
  const q = query.q.trim().toLowerCase();
  if (q) p.set("q", q);
  if (query.status) p.set("status", query.status);
  if (query.hasSet) p.set("has_set", "true");
  p.set("limit", String(query.limit));
  if (query.offset) p.set("offset", String(query.offset));
  return `modelkit/drugs?${p.toString()}`;
}

/** The same filter and page the API applies, over a full list (the recorded demo answer). */
export function pageOfDrugs(all: DrugsOut, query: DrugsQuery): DrugsOut {
  const q = query.q.trim().toLowerCase();
  const kept = all.drugs.filter(
    (d) =>
      (!q ||
        d.key.includes(q.replaceAll(" ", "_")) ||
        d.name.toLowerCase().includes(q)) &&
      (!query.status || d.status === query.status) &&
      (!query.hasSet || d.has_set),
  );
  const counts: Record<string, number> = {
    all: all.drugs.length,
    with_set: all.drugs.filter((d) => d.has_set).length,
  };
  for (const st of STATUSES)
    counts[st] = all.drugs.filter((d) => d.status === st).length;
  return {
    ...all,
    drugs: kept.slice(query.offset, query.offset + query.limit),
    total: kept.length,
    offset: query.offset,
    limit: query.limit,
    counts,
  };
}

export interface ModelKitClient {
  /** True when the zip downloads can be offered (live service only). */
  downloads: boolean;
  drugs(query: DrugsQuery): Promise<Result<DrugsOut>>;
  system(): Promise<Result<SystemOut>>;
  drug(key: string): Promise<Result<DrugOut>>;
  evidence(key: string): Promise<Result<EvidenceOut>>;
  exportUrl(key: string, target: Target): string;
}

export const KEY = /^[a-z][a-z0-9_]{0,31}$/;

/** The drug key of a URL fragment (`#sunitinib`); null when it is not a valid key. */
export function keyFromHash(hash: string): string | null {
  const v = hash.replace(/^#/, "");
  return KEY.test(v) ? v : null;
}

const http = new HttpClient();
const buildError = (route: "modelkit/drug" | "modelkit/evidence") =>
  ({
    ok: false,
    error: { kind: "build", route, messageKey: "Errors.client_defect" },
  }) as const;

export const liveModelKit: ModelKitClient = {
  downloads: true,
  drugs: (query) =>
    http.call(
      "modelkit/drugs",
      "GET",
      null,
      drugsOut,
      undefined,
      drugsPath(query),
    ),
  system: () => http.call("modelkit/validation", "GET", null, systemOut),
  drug: async (key) =>
    KEY.test(key)
      ? http.call(
          "modelkit/drug",
          "GET",
          null,
          drugOut,
          undefined,
          `modelkit/drugs/${key}`,
        )
      : buildError("modelkit/drug"),
  evidence: async (key) =>
    KEY.test(key)
      ? http.call(
          "modelkit/evidence",
          "GET",
          null,
          evidenceOut,
          undefined,
          `modelkit/drugs/${key}/evidence`,
        )
      : buildError("modelkit/evidence"),
  exportUrl: (key, target) => `/api/modelkit/drugs/${key}/export/${target}`,
};

export function demoModelKit(fx: ModelKitFixture): ModelKitClient {
  const contract = (route: "modelkit/drugs" | "modelkit/validation") =>
    ({
      ok: false,
      error: { kind: "contract", route, messageKey: "Errors.generic" },
    }) as const;
  const unknown = (route: "modelkit/drug" | "modelkit/evidence") =>
    ({
      ok: false,
      error: {
        kind: "http",
        route,
        status: 404,
        code: "unknown_drug",
        fields: [] as string[],
        messageKey: "ModelKit.errors.unknown",
      },
    }) as const;
  const answer = async <T>(
    d: D.Decoder<T>,
    raw: unknown,
    route: "modelkit/drugs" | "modelkit/validation",
  ): Promise<Result<T>> => {
    const r = D.decode(d, raw);
    return r.ok ? { ok: true, data: r.value } : contract(route);
  };
  const byKey = async <T>(
    d: D.Decoder<T>,
    all: Record<string, unknown>,
    key: string,
    route: "modelkit/drug" | "modelkit/evidence",
  ): Promise<Result<T>> => {
    if (!Object.hasOwn(all, key)) return unknown(route);
    const r = D.decode(d, all[key]);
    return r.ok
      ? { ok: true, data: r.value }
      : {
          ok: false,
          error: { kind: "contract", route, messageKey: "Errors.generic" },
        };
  };
  return {
    downloads: false,
    drugs: async (query) => {
      const r = await answer(drugsOut, fx.drugs, "modelkit/drugs");
      return r.ok ? { ok: true, data: pageOfDrugs(r.data, query) } : r;
    },
    system: () => answer(systemOut, fx.validation, "modelkit/validation"),
    drug: (k) => byKey(drugOut, fx.drug, k, "modelkit/drug"),
    evidence: (k) => byKey(evidenceOut, fx.evidence, k, "modelkit/evidence"),
    exportUrl: () => "",
  };
}

export function loadModelKitFixture(): Promise<ModelKitFixture> {
  return import("./modelkit.recorded.json").then(
    (m) => m.default as unknown as ModelKitFixture,
  );
}

// --- view model ----------------------------------------------------------------------------------

export type Tone = "validated" | "not_validated" | "failed";

/** Message key and presentation of a status. Never red: red is for real risk only. */
export function statusBadge(s: Status): { labelKey: string; tone: Tone } {
  return { labelKey: `ModelKit.status.${s}`, tone: s };
}

/** Every reason code the API can send; each has a message in `ModelKit.reasons`. */
export const REASON_CODES = [
  "not_confirmed",
  "analyte_not_parent",
  "coadministered",
  "fixed_dose_combination",
  "formulation_not_immediate_release",
  "bound_not_a_value",
  "per_kg_not_converted",
  "held_out_study",
  "observation_in_building_study",
  "not_needed_preferred_basis",
  "auc_to_last_sampling_time_not_comparable",
  "not_an_observation",
  "needs_oral_dose",
  "auc_tau_needs_multiple_dose_interval",
  "steady_state_cmax_not_modelled",
  "auc_inf_needs_single_dose",
  "set_has_no_absorption_rate",
  "set_cannot_predict_metric",
  "no_parameter_set",
  "no_independent_observation",
  "auc_not_tested",
  "cmax_not_tested",
  "point_outside_2_fold",
  "all_points_within_2_fold",
  "no_confirmed_clearance",
  "no_confirmed_volume",
  "iv_evidence_incomplete",
  "iv_without_bioavailability",
  "no_volume_and_no_half_life",
  "missing_absorption_no_peak_time",
  "missing_absorption_no_solution",
  "bioavailability_capped",
  "half_life_inconsistent",
  "studies_disagree",
  "healthy_adult_preferred",
  "no_central_volume_evidence",
  "two_volumes_differ",
  "two_volumes_agree",
  "v_from_clf_half_life",
  "cl_from_dose_and_auc",
  "ka_from_tmax",
  "f_fixed_apparent",
  "clearance_or_bioavailability",
  "absorption_rate_or_volume",
  "n_very_small",
  "two_automated_passes",
  "confirmed_precision_below_target",
  "expert_review_pending",
  "sp_statements_note",
  "sp_atlas_note",
  "sp_none",
  "two_readers_agree",
  "automated_extraction_unconfirmed",
  "interval_n_too_small",
  "interval_system_level_only",
  "interval_shown",
  "gate_not_interpretable",
  "no_drug_validated",
  "intervals_not_shown",
  "formulation_often_unspecified",
  "fewer_than_150_sets",
  "not_used",
] as const;

const KNOWN = new Set<string>(REASON_CODES);

/** The message key of a reason code, or null for a code this version does not know. */
export function reasonKey(code: string): string | null {
  return KNOWN.has(code) ? `ModelKit.reasons.${code}` : null;
}

export const PARAM_NAMES = ["cl", "v", "f", "ka"] as const;

/** Message key of a parameter label; apparent oral values are labelled CL/F, V/F. */
export function paramKey(name: string, apparent: boolean): string | null {
  if (!(PARAM_NAMES as readonly string[]).includes(name)) return null;
  return `ModelKit.param.${apparent && name !== "ka" ? `${name}Apparent` : name}`;
}

export const EVIDENCE_PARAMS = [
  "cl",
  "cl_f",
  "vss",
  "vd",
  "v_f",
  "t_half",
  "tmax",
  "f",
  "cmax",
  "auc_inf",
  "auc_last",
  "auc_tau",
  "cl_per_kg",
  "vd_per_kg",
] as const;

/** Rows by id, for the evidence behind a value. */
export function rowsById(
  rows: readonly EvidenceRow[],
): Map<string, EvidenceRow> {
  return new Map(rows.map((r) => [r.id, r]));
}

// --- chart: observed against predicted, log-log, 2-fold band -------------------------------------

export interface LogAxis {
  min: number;
  max: number;
  /** One tick per decade. */
  ticks: number[];
}

/**
 * One axis for both directions (a square plot, so y = x is the diagonal): whole decades around
 * every observed and predicted value, at least one decade wide.
 */
export function logAxis(values: readonly number[]): LogAxis {
  const v = values.filter((x) => Number.isFinite(x) && x > 0);
  if (!v.length) return { min: 1, max: 10, ticks: [1, 10] };
  const lo = Math.floor(Math.log10(Math.min(...v)) + 1e-9);
  let hi = Math.ceil(Math.log10(Math.max(...v)) - 1e-9);
  if (hi <= lo) hi = lo + 1;
  const ticks: number[] = [];
  for (let d = lo; d <= hi; d++) ticks.push(10 ** d);
  return { min: 10 ** lo, max: 10 ** hi, ticks };
}

/** Position 0-1 of a value on a log axis, clamped. */
export function logPos(axis: LogAxis, v: number): number {
  if (!Number.isFinite(v) || v <= 0) return 0;
  const f =
    (Math.log10(v) - Math.log10(axis.min)) /
    (Math.log10(axis.max) - Math.log10(axis.min));
  return Math.min(1, Math.max(0, f));
}

/**
 * The band between y = x / 2 and y = 2x, clipped to the square, as a closed polygon in data space.
 * Needs max / min >= 4, which `logAxis` guarantees (at least one decade).
 */
export function bandPolygon(axis: LogAxis): [number, number][] {
  const { min, max } = axis;
  return [
    [min, min],
    [min, 2 * min],
    [max / 2, max],
    [max, max],
    [max, max / 2],
    [2 * min, min],
  ];
}

/** Whether a point lies in the 2-fold band (inclusive), by its ratio predicted / observed. */
export function inBand(p: Pick<PointOut, "observed" | "predicted">): boolean {
  const r = p.predicted / p.observed;
  return r >= 0.5 - 1e-12 && r <= 2 + 1e-12;
}

/** A long internal study id shortened for display (a UUID keeps its first eight characters, any
 * other id over 16 characters is cut); the full id stays in the evidence panel and as a title. */
export function shortStudy(id: string): string {
  if (
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)
  )
    return `${id.slice(0, 8)}…`;
  return id.length > 16 ? `${id.slice(0, 15)}…` : id;
}

/**
 * Light-face answers (light-face design §9): decoders written from the Pydantic models in
 * `apps/api/janus/light/schemas.py`, types inferred from them so the two cannot drift apart.
 * Only the fields the screens read are decoded; the rest of an answer is ignored.
 */
import {
  arr,
  bool,
  int,
  lit,
  nullable,
  num,
  obj,
  record,
  stats,
  str,
  type Infer,
} from "@/api/decode";

const strs = arr(str);
const labels = record(str);
const rank = obj({ best: int, worst: int, population: int });

export const snapshot = obj({
  build_id: str,
  onsides_release: str,
  onsides_date: str,
  faers_snapshot_date: str,
  faers_window: strs,
  openfda_date: str,
});

const common = {
  status: lit("experimental", "prototype"),
  review_status: lit("ai_reviewed_pending_expert"),
  snapshot,
  codes: strs,
  disclaimer: str,
  attribution: strs,
};

export const goalSummary = obj({
  key: str,
  labels,
  candidates: int,
  label_terms: strs,
  faers_pts: strs,
  benefit_keys: strs,
  inverse_tested: int,
  inverse_found: int,
  inverse_expected_by_chance: num,
});

export const overviewOut = obj({
  ...common,
  goals: arr(goalSummary),
  top_k: int,
});

const labelSignal = obj({
  regions: strs,
  labels_with_effect: int,
  labels_total: int,
  share_low: num,
  sections: strs,
  terms: strs,
  evidence_ids: strs,
  nonspecific: bool,
});

const inverseSignal = obj({
  stats,
  pts: strs,
  reports: int,
  expected: num,
  observed_over_expected: num,
  upper_bound_sensitive: bool,
  evidence_ids: strs,
  locator: str,
});

const patientSignal = obj({
  event: str,
  total_of_released: int,
  cells: arr(
    obj({
      region: str,
      status: lit("released", "hidden"),
      value: nullable(int),
    }),
  ),
  k: int,
  epsilon: str,
});

export const source = obj({
  id: str,
  title: nullable(str),
  doi: nullable(str),
  url: str,
  status: str,
  snapshot_date: str,
});

const ref = obj({ key: str, labels });

export const card = obj({
  ingredient: ref,
  goal: ref,
  rank,
  signals: arr(
    obj({
      type: lit("label_effect", "inverse_faers", "patient_reported"),
      label: nullable(labelSignal),
      inverse: nullable(inverseSignal),
      patient: nullable(patientSignal),
      codes: strs,
    }),
  ),
  sources: arr(source),
  removed_sources: arr(obj({ id: str, reason: str })),
  codes: strs,
});

export const cardsOut = obj({
  ...common,
  goal: ref,
  total: int,
  offset: int,
  cards: arr(card),
  patient_reported: arr(
    obj({ ingredient: ref, goal: ref, signal: patientSignal, codes: strs }),
  ),
  patient_layer: lit("ok", "layer_unavailable"),
  removed_by_integrity: int,
  warning_sources: arr(source),
});

const reason = lit(
  "hit",
  "ranked_below_top",
  "not_a_candidate",
  "no_label_mapping",
  "not_evaluable",
);

const caseRun = obj({
  run: lit("primary", "primary_indication", "primary_strict", "sensitivity"),
  rank: nullable(rank),
  population: int,
  hit: bool,
  informative: bool,
  labels_used: int,
  labels_removed_indication: int,
  labels_removed_not_in_openfda: int,
  signal_types: strs,
  reason,
  chance_hit: nullable(num),
  percentile: nullable(num),
});

const summary = obj({
  hits: int,
  informative_hits: int,
  misses: int,
  not_evaluable: int,
  expected_hits_by_chance: num,
});

export const validationOut = obj({
  ...common,
  top_k: int,
  cases: arr(
    obj({
      case: obj({
        id: str,
        ingredient_name: str,
        ingredient_key: str,
        goal: str,
        original_use: str,
        later_year: int,
        evidence_ids: strs,
        note: str,
      }),
      primary: caseRun,
      primary_indication: caseRun,
      primary_strict: caseRun,
      sensitivity: caseRun,
      faers: nullable(stats),
      faers_inverse: bool,
      faers_includes_later_use: bool,
    }),
  ),
  primary: summary,
  sensitivity: summary,
  goals: arr(ref),
  ingredients: record(labels),
  sources: arr(source),
});

export const exportRow = obj({
  goal: str,
  ingredient: str,
  ingredient_name_en: str,
  rank_best: int,
  rank_worst: int,
  population: int,
  signal_types: strs,
  label_regions: strs,
  labels_with_effect: nullable(int),
  labels_total: nullable(int),
  label_terms: strs,
  faers_reports: nullable(int),
  faers_ror: nullable(num),
  faers_ror_low: nullable(num),
  faers_ror_high: nullable(num),
  patient_reported_released: nullable(int),
  source_ids: strs,
});

export const exportOut = obj({
  ...common,
  licence: str,
  rows: arr(exportRow),
  goals: arr(goalSummary),
});

export type LightSnapshot = Infer<typeof snapshot>;
export type GoalSummary = Infer<typeof goalSummary>;
export type OverviewOut = Infer<typeof overviewOut>;
export type Card = Infer<typeof card>;
export type CardSignal = Card["signals"][number];
export type Source = Infer<typeof source>;
export type CardsOut = Infer<typeof cardsOut>;
export type ValidationOut = Infer<typeof validationOut>;
export type CaseResult = ValidationOut["cases"][number];
export type CaseRun = CaseResult["primary"];
export type ExportOut = Infer<typeof exportOut>;
export type ExportRow = Infer<typeof exportRow>;
export type Rank = Infer<typeof rank>;

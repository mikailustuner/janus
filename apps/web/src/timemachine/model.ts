/**
 * The time-machine contract (time-machine design §10, experience Req 30). Read-only GET answers;
 * every number is the API's, the client derives none (design §1: the pure maths lives in the API).
 */
import * as D from "@/api/decode";

const band = D.obj({ p5: D.num, p50: D.num, p95: D.num });

export const meta = D.obj({
  built_at: D.str,
  review_status: D.lit("Expert review has not yet been done"),
  disclaimer: D.str,
  seed: D.int,
  simulations: D.int,
});

const validationRow = D.obj({
  drug: D.str,
  reference_key: D.str,
  observed_cmax_ng_ml: D.nullable(D.num),
  predicted_cmax_ng_ml: D.nullable(D.num),
  cmax_fold_error: D.nullable(D.num),
  observed_auc_ng_h_ml: D.nullable(D.num),
  predicted_auc_ng_h_ml: D.nullable(D.num),
  auc_fold_error: D.nullable(D.num),
  credibility: D.lit("credible", "borderline", "failed"),
  note: D.str,
});

const summary = D.record(D.int);

export const validation = D.obj({
  rule: D.str,
  pbpk: D.arr(validationRow),
  compartmental: D.arr(validationRow),
  pbpk_summary: summary,
  compartmental_summary: summary,
});

const sourceInfo = D.obj({
  run_id: D.nullable(D.str),
  snapshot_date: D.nullable(D.str),
  license: D.nullable(D.str),
  source_urls: D.arr(D.str),
  tool_versions: D.nullable(D.record(D.str)),
});

export const catalogue = D.obj({
  meta,
  substance_ids: D.arr(D.str),
  cascade_ids: D.arr(D.str),
  validation,
  sources: D.record(sourceInfo),
  onset_subset_caveat: D.str,
});

const reference = D.obj({
  key: D.str,
  citation: D.str,
  doi_or_url: D.str,
  verified: D.str,
  note: D.str,
});

const constituent = D.obj({
  compound: D.str,
  pubchem_cid: D.nullable(D.str),
  inchikey: D.nullable(D.str),
  wikidata_qid: D.nullable(D.str),
  taxon_qids: D.arr(D.str),
  occurrence_reference_qids: D.arr(D.str),
  why_selected: D.str,
  molecular_weight: D.nullable(D.num),
  admet: D.nullable(D.record(D.num)),
  measured_activities: D.arr(
    D.obj({
      gene: D.nullable(D.str),
      target: D.nullable(D.str),
      measure: D.str,
      value_um: D.nullable(D.num),
      outcome: D.str,
      assay: D.str,
      depositor: D.str,
      aid: D.str,
    }),
  ),
  measured_activity_count: D.int,
  interaction_flags: D.arr(
    D.obj({
      gene: D.str,
      entrez_gene: D.nullable(D.str),
      measure: D.str,
      pubchem_aid: D.nullable(D.str),
      value_withheld_licence: D.nullable(D.str),
      established: D.bool,
      evidence_reference_key: D.nullable(D.str),
      meaning: D.str,
    }),
  ),
});

const exposure = D.obj({
  constituent: D.str,
  historical_dose: D.obj({
    amount: D.num,
    unit: D.str,
    grams_low: D.num,
    grams_central: D.num,
    grams_high: D.num,
    unit_sources: D.arr(D.str),
  }),
  constituent_dose_mg: D.obj({ low: D.num, high: D.num }),
  content_percent: D.obj({ low: D.num, high: D.num }),
  reference_keys: D.arr(D.str),
  note: D.str,
  model: D.nullable(
    D.obj({
      kind: D.lit("compartmental"),
      label: D.str,
      peak_mg_per_l: band,
      tmax_h: D.num,
      parameter_sources: D.arr(D.str),
    }),
  ),
  model_validated: D.bool,
  not_validated_reason: D.optional(D.str),
  no_potency_reason: D.optional(D.str),
  curated_targets: D.optional(D.arr(D.str)),
  comparison: D.optional(
    D.nullable(
      D.obj({
        verdict: D.lit("reaches", "overlaps", "stays_below"),
        basis: D.lit("unbound", "total_only"),
        margin_low: D.num,
        margin_high: D.num,
        potency_um: D.num,
        potency_measure: D.str,
        potency_assay: D.str,
        potency_aid: D.str,
        unbound_fraction_source: D.nullable(D.str),
      }),
    ),
  ),
});

export const substanceOut = D.obj({
  meta,
  substance: D.obj({
    substance_id: D.str,
    constituents: D.arr(constituent),
    todays_drugs: D.arr(
      D.obj({
        drug: D.str,
        condition_key: D.str,
        indication_term: D.str,
        label_set_id: D.nullable(D.str),
        label_effective_time: D.nullable(D.str),
        bridge_note: D.str,
      }),
    ),
  }),
  exposure: D.arr(exposure),
  references: D.arr(reference),
});

const onset = D.obj({
  reports: D.int,
  median_days: D.num,
  q25_days: D.num,
  q75_days: D.num,
  median_ci_low: D.nullable(D.num),
  median_ci_high: D.nullable(D.num),
  small_sample: D.bool,
  zero_day_reports: D.int,
  zero_day_caveat: D.str,
  weibull: D.nullable(
    D.obj({
      shape: D.num,
      shape_ci_low: D.nullable(D.num),
      shape_ci_high: D.nullable(D.num),
      scale: D.num,
      shape_class: D.lit("early", "random", "wear_out"),
    }),
  ),
  weibull_omitted_reason: D.nullable(D.str),
});

export const cascadeOut = D.obj({
  meta,
  cascade: D.obj({
    cascade_id: D.str,
    pipc_position: D.int,
    index_class: D.str,
    event: D.str,
    treating_class: D.str,
    method: D.lit("pbpk", "compartmental", "onset_only"),
    method_label: D.str,
    note: D.str,
    reference_keys: D.arr(D.str),
    onset: D.nullable(onset),
    risk_window: D.nullable(
      D.obj({
        start_days: D.num,
        end_days: D.num,
        basis: D.lit("weibull", "reports"),
        coverage: D.str,
      }),
    ),
    middle_half_days: D.optional(
      D.nullable(D.obj({ start_days: D.num, end_days: D.num })),
    ),
    onset_curve: D.nullable(D.obj({ days: D.arr(D.num), share: D.arr(D.num) })),
    published: D.nullable(
      D.obj({
        kind: D.lit("median_iqr", "window", "qualitative"),
        low_days: D.nullable(D.num),
        high_days: D.nullable(D.num),
        median_days: D.nullable(D.num),
        reference_keys: D.arr(D.str),
      }),
    ),
    agreement: D.nullable(D.lit("agrees", "disagrees", "not_comparable")),
    population: D.nullable(
      D.obj({
        age_range_older: D.str,
        age_range_younger: D.str,
        source: D.str,
        dose_basis: D.str,
        drugs: D.arr(
          D.obj({
            drug: D.str,
            css_older_mg_per_l: band,
            css_younger_mg_per_l: band,
            older_to_younger_ratio: D.num,
            days_to_90pct_steady_state: D.nullable(D.num),
          }),
        ),
      }),
    ),
  }),
  faers_quality: D.nullable(
    D.obj({
      reports: D.int,
      usable_pairs: D.int,
      usable_pair_share: D.num,
      complete_event_date_share: D.num,
      window: D.arr(D.str),
      rule: D.str,
    }),
  ),
  onset_subset_caveat: D.str,
  references: D.arr(reference),
});

export type Catalogue = D.Infer<typeof catalogue>;
export type SubstanceOut = D.Infer<typeof substanceOut>;
export type CascadeOut = D.Infer<typeof cascadeOut>;
export type Cascade = CascadeOut["cascade"];
export type Exposure = SubstanceOut["exposure"][number];
export type Constituent = SubstanceOut["substance"]["constituents"][number];
export type ValidationRow = Catalogue["validation"]["pbpk"][number];
export type Reference = SubstanceOut["references"][number];

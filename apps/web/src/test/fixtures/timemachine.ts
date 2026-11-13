/**
 * Synthetic time-machine answers (catalogue, two substances, three cascades) for the behaviour
 * tests. Typed with the production types and decoded by the production decoders; nothing is read
 * from the recorded file.
 *
 * - `rhubarb`: a compartmental model that is validated and has no measured potency (the gap is
 *   shown, never a verdict)
 * - `anise`: no human PK parameters (the reason is shown in place of a verdict)
 * - `amlodipine_oedema_diuretic`: compartmental, 35 reports, not a small sample, agrees with the
 *   published window; passes the patient gate (middle half 7 to 104 days)
 * - `antipsychotic_eps_antiparkinson`: PBPK, small sample (no shape class), two drugs
 * - `metoclopramide_eps_antiparkinson`: PBPK, no onset data
 * The validation table has 2 compartmental rows (1 credible, 1 borderline) and 4 PBPK rows
 * (1 borderline, 3 failed).
 */
import * as D from "@/api/decode";
import type { TimeMachineFixture } from "@/timemachine/client";
import {
  cascadeOut,
  catalogue,
  substanceOut,
  type CascadeOut,
  type Catalogue,
  type SubstanceOut,
  type ValidationRow,
} from "@/timemachine/model";

function checked<T>(decoder: D.Decoder<T>, value: T, what: string): T {
  const r = D.decode(decoder, value);
  if (!r.ok) throw new Error(`synthetic fixture ${what} does not decode`);
  return value;
}

const meta = {
  built_at: "2026-01-01T00:00:00+00:00",
  review_status: "Expert review has not yet been done" as const,
  disclaimer:
    "In-silico hypotheses from open data. Not a treatment, not a dose, not medical advice. Research prototype, not a medical device.",
  seed: 1,
  simulations: 2000,
};
const SUBSET_CAVEAT =
  "Time to onset is available only for reports whose reporter gave both a therapy start and an event date.";

const reference = (key: string) => ({
  key,
  citation: `Synthetic Author. Synthetic reference ${key}.`,
  doi_or_url: "https://example.org/reference",
  verified: "text read 2026-01-01",
  note: "",
});

const row = (
  drug: string,
  credibility: ValidationRow["credibility"],
): ValidationRow => ({
  drug,
  reference_key: `synthetic_${drug}`,
  observed_cmax_ng_ml: 10,
  predicted_cmax_ng_ml: credibility === "failed" ? 40 : 12,
  cmax_fold_error: credibility === "failed" ? 4 : 1.2,
  observed_auc_ng_h_ml: 100,
  predicted_auc_ng_h_ml: 90,
  auc_fold_error: 1.1,
  credibility,
  note: "synthetic validation row",
});

function summaryOf(rows: ValidationRow[]) {
  const n = (c: ValidationRow["credibility"]) =>
    rows.filter((r) => r.credibility === c).length;
  return {
    credible: n("credible"),
    borderline: n("borderline"),
    failed: n("failed"),
  };
}

export function catalogueOf(): Catalogue {
  const compartmental = [
    row("amlodipine", "borderline"),
    row("caffeine", "credible"),
  ];
  const pbpk = [
    row("risperidone", "failed"),
    row("haloperidol", "failed"),
    row("olanzapine", "failed"),
    row("metoclopramide", "borderline"),
  ];
  return checked(
    catalogue,
    {
      meta,
      substance_ids: ["anise", "rhubarb"],
      cascade_ids: [
        "amlodipine_oedema_diuretic",
        "antipsychotic_eps_antiparkinson",
        "metoclopramide_eps_antiparkinson",
      ],
      validation: {
        rule: "credible when predicted Cmax and AUC are both within 2-fold of the published observed values",
        pbpk,
        compartmental,
        pbpk_summary: summaryOf(pbpk),
        compartmental_summary: summaryOf(compartmental),
      },
      sources: {
        faers: {
          run_id: "20260101T000000Z-synthetic",
          snapshot_date: "2026-01-01",
          license: "CC0 1.0",
          source_urls: ["https://example.org/faers"],
          tool_versions: null,
        },
      },
      onset_subset_caveat: SUBSET_CAVEAT,
    },
    "catalogue",
  );
}

const constituent = (compound: string, qid: string) => ({
  compound,
  pubchem_cid: "1",
  inchikey: "AAAAAAAAAAAAAA-BBBBBBBBBB-N",
  wikidata_qid: qid,
  taxon_qids: ["Q1"],
  occurrence_reference_qids: ["Q2"],
  why_selected: "Synthetic: the expression unit of the preparation.",
  molecular_weight: 284.2,
  admet: { Half_Life_Obach: 25.4, VDss_Lombardo: 0.18 },
  measured_activities: [
    {
      gene: null,
      target: "SYN_A",
      measure: "Potency",
      value_um: 0.3,
      outcome: "Active",
      assay: "synthetic screening assay",
      depositor: "synthetic depositor",
      aid: "1",
    },
  ],
  measured_activity_count: 1,
  interaction_flags: [
    {
      gene: "CYP1A2",
      entrez_gene: "1544",
      measure: "Potency",
      pubchem_aid: "2",
      value_withheld_licence: "unverified",
      established: false,
      evidence_reference_key: null,
      meaning:
        "a record of activity on a drug-metabolism target: a signal to check",
    },
  ],
});

const exposureBase = (substanceId: string, compound: string) => ({
  constituent: compound,
  historical_dose: {
    amount: 2,
    unit: "dirham",
    grams_low: 5.6,
    grams_central: 5.95,
    grams_high: 6.6,
    unit_sources: ["synthetic_unit"],
  },
  constituent_dose_mg: { low: 168, high: 792 },
  content_percent: { low: 3, high: 12 },
  reference_keys: ["synthetic_unit"],
  note: "Synthetic note for the historical dose.",
  substance_id: substanceId,
});

export function rhubarbOf(): SubstanceOut {
  return checked(
    substanceOut,
    {
      meta,
      substance: {
        substance_id: "rhubarb",
        constituents: [constituent("rhein", "Q720356")],
        todays_drugs: [
          {
            drug: "ibuprofen",
            condition_key: "muscle_injury",
            indication_term: "pain",
            label_set_id: "00000000-0000-4000-8000-000000000001",
            label_effective_time: "20260101",
            bridge_note: "Synthetic bridge note.",
          },
        ],
      },
      exposure: [
        {
          ...exposureBase("rhubarb", "rhein"),
          comparison: null,
          model: {
            kind: "compartmental",
            label:
              "minimal compartmental model with cited physiological parameters (not PBPK)",
            peak_mg_per_l: { p5: 19.7, p50: 32.1, p95: 52.1 },
            tmax_h: 1.97,
            parameter_sources: ["synthetic_unit"],
          },
          model_validated: true,
          no_potency_reason:
            "no measured potency on a curated, condition-relevant target from a public-domain depositor",
          curated_targets: ["3553"],
        },
      ],
      references: [reference("synthetic_unit")],
    },
    "substance rhubarb",
  );
}

export function aniseOf(): SubstanceOut {
  return checked(
    substanceOut,
    {
      meta,
      substance: {
        substance_id: "anise",
        constituents: [constituent("trans-anethole", "Q255564")],
        todays_drugs: [],
      },
      exposure: [
        {
          ...exposureBase("anise", "trans-anethole"),
          comparison: null,
          model: null,
          model_validated: false,
          not_validated_reason:
            "no published human PK parameters for this constituent",
        },
      ],
      references: [reference("synthetic_unit")],
    },
    "substance anise",
  );
}

const onsetCurve = {
  days: [0, 7, 14, 21, 28, 42, 56, 84, 120, 180, 270, 365],
  share: [0.07, 0.25, 0.36, 0.44, 0.5, 0.6, 0.68, 0.78, 0.86, 0.93, 0.97, 1],
};

const faersQuality = {
  reports: 1000,
  usable_pairs: 100,
  usable_pair_share: 0.09,
  complete_event_date_share: 0.43,
  window: ["2025Q4", "2026Q1"],
  rule: "earliest complete therapy start date of the drug; event date; 0 <= days",
};

const band = (p5: number, p50: number, p95: number) => ({ p5, p50, p95 });
const cssDrug = (drug: string, days: number) => ({
  drug,
  css_older_mg_per_l: band(0.35, 1.06, 5),
  css_younger_mg_per_l: band(0.21, 0.67, 3.5),
  older_to_younger_ratio: 1.58,
  days_to_90pct_steady_state: days,
});

const onsetOf = (reports: number, small: boolean) => ({
  reports,
  median_days: 23,
  q25_days: 7,
  q75_days: 104,
  median_ci_low: 21,
  median_ci_high: 73,
  small_sample: small,
  zero_day_reports: 4,
  zero_day_caveat:
    "a same-day interval often means the reporter gave one date for both fields",
  weibull: small
    ? null
    : {
        shape: 0.5,
        shape_ci_low: 0.38,
        shape_ci_high: 0.64,
        scale: 90,
        shape_class: "early" as const,
      },
  weibull_omitted_reason: small ? "no shape below 30 reports" : null,
});

const cascadeBase = {
  event: "Peripheral oedema",
  index_class: "Calcium channel blocker",
  treating_class: "Diuretic",
  note: "Synthetic note.",
  reference_keys: ["synthetic_unit"],
};

export function amlodipineOf(): CascadeOut {
  return checked(
    cascadeOut,
    {
      meta,
      cascade: {
        ...cascadeBase,
        cascade_id: "amlodipine_oedema_diuretic",
        pipc_position: 5,
        method: "compartmental",
        method_label:
          "minimal compartmental model with cited physiological parameters (not PBPK)",
        onset: onsetOf(35, false),
        risk_window: {
          start_days: 0.5,
          end_days: 475,
          basis: "weibull",
          coverage: "central 80 percent of the reported intervals",
        },
        middle_half_days: { start_days: 7, end_days: 104 },
        onset_curve: onsetCurve,
        published: {
          kind: "window",
          low_days: 1,
          high_days: 120,
          median_days: null,
          reference_keys: ["synthetic_unit"],
        },
        agreement: "agrees",
        population: null,
      },
      faers_quality: faersQuality,
      onset_subset_caveat: SUBSET_CAVEAT,
      references: [reference("synthetic_unit")],
    },
    "cascade amlodipine",
  );
}

export function antipsychoticOf(): CascadeOut {
  return checked(
    cascadeOut,
    {
      meta,
      cascade: {
        ...cascadeBase,
        event: "Extrapyramidal symptoms",
        index_class: "Antipsychotic",
        treating_class: "Antiparkinsonian agent",
        cascade_id: "antipsychotic_eps_antiparkinson",
        pipc_position: 18,
        method: "pbpk",
        method_label:
          "PBPK (httk) for the index drug, plus FAERS time to onset",
        onset: onsetOf(29, true),
        risk_window: {
          start_days: 0,
          end_days: 74,
          basis: "weibull",
          coverage: "central 80 percent of the reported intervals",
        },
        middle_half_days: { start_days: 0, end_days: 20 },
        onset_curve: onsetCurve,
        published: {
          kind: "qualitative",
          low_days: null,
          high_days: null,
          median_days: null,
          reference_keys: ["synthetic_unit"],
        },
        agreement: "not_comparable",
        population: {
          age_range_older: "65-79",
          age_range_younger: "20-50",
          source:
            "Synthetic virtual individuals; ages above 79 are not covered",
          dose_basis: "1 mg/kg/day, steady state; relative comparison only",
          drugs: [cssDrug("haloperidol", 20), cssDrug("risperidone", 4)],
        },
      },
      faers_quality: faersQuality,
      onset_subset_caveat: SUBSET_CAVEAT,
      references: [reference("synthetic_unit")],
    },
    "cascade antipsychotic",
  );
}

/** A PBPK cascade for metoclopramide with no onset data: its page shows the label half-life. */
export function metoclopramideOf(): CascadeOut {
  return checked(
    cascadeOut,
    {
      meta,
      cascade: {
        ...cascadeBase,
        event: "Extrapyramidal symptoms",
        index_class: "Metoclopramide",
        treating_class: "Antiparkinsonian agent",
        cascade_id: "metoclopramide_eps_antiparkinson",
        pipc_position: 18,
        method: "pbpk",
        method_label:
          "PBPK (httk) for the index drug, plus FAERS time to onset",
        onset: null,
        risk_window: null,
        onset_curve: null,
        published: null,
        agreement: null,
        population: {
          age_range_older: "65-79",
          age_range_younger: "20-50",
          source:
            "Synthetic virtual individuals; ages above 79 are not covered",
          dose_basis: "1 mg/kg/day, steady state; relative comparison only",
          drugs: [cssDrug("metoclopramide", 6)],
        },
      },
      faers_quality: faersQuality,
      onset_subset_caveat: SUBSET_CAVEAT,
      references: [reference("synthetic_unit")],
    },
    "cascade metoclopramide",
  );
}

export function timeMachineSet(): TimeMachineFixture & {
  catalogue: Catalogue;
  substances: Record<string, SubstanceOut>;
  cascades: Record<string, CascadeOut>;
} {
  return {
    recorded: "synthetic",
    catalogue: catalogueOf(),
    substances: { rhubarb: rhubarbOf(), anise: aniseOf() },
    cascades: {
      amlodipine_oedema_diuretic: amlodipineOf(),
      antipsychotic_eps_antiparkinson: antipsychoticOf(),
      metoclopramide_eps_antiparkinson: metoclopramideOf(),
    },
  };
}

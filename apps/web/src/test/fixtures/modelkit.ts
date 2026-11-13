/**
 * Synthetic model-kit answers for the behaviour tests (unit and e2e). Hand-built, small, typed with
 * the production types and decoded by the production decoders, so a fixture that drifts from the
 * contract fails type-check or throws on load. Nothing here is read from a recorded file: the
 * recorded release changes with every pipeline run, these answers do not.
 *
 * What the set covers, by drug key:
 * - `ertugliflozin`  validated, intravenous set, two AUC points and one Cmax point, half-life warning
 * - `sunitinib`      failed (one Cmax point outside 2-fold, suspect parameter), oral apparent set
 * - `dolutegravir`   not validated with a set (Cmax not tested)
 * - `gabapentin`     no parameter set (reasons, evidence rows, no chart)
 * - `repaglinide`    set with a point exactly on the 2-fold edge, 24 excluded evidence rows
 * - `metformin`      eight special-population statements (all classes) and two atlas rows
 * - `amlodipine`     three special-population statements, no atlas row
 * - 22 filler drugs  without a set, so the list has two pages
 */
import * as D from "@/api/decode";
import {
  drugOut,
  drugsOut,
  evidenceOut,
  systemOut,
  type DrugOut,
  type DrugsOut,
  type DrugSummary,
  type EvidenceOut,
  type EvidenceRow,
  type ExpertAudit,
  type IntervalOut,
  type MetricOut,
  type ModelKitFixture,
  type ParamOut,
  type PointOut,
  type SpecialAtlas,
  type SpecialStatement,
  type Status,
  type SystemOut,
} from "@/modelkit/model";

/** Decodes with the production decoder; a drifted fixture throws here. */
function checked<T>(decoder: D.Decoder<T>, value: T, what: string): T {
  const r = D.decode(decoder, value);
  if (!r.ok) throw new Error(`synthetic fixture ${what} does not decode`);
  return value;
}

const RELEASE = {
  run_id: "20260101T000000Z-synthetic",
  snapshot_date: "2026-01-01",
  pipeline_version: "modelkit-evidence-test",
};

/** The expert audit record of the review line (a fixed one, for the audit tests). */
export const AUDIT: ExpertAudit = {
  date: "2027-01-15",
  release_audited: "20260101T000000Z-synthetic",
  n_items: 366,
  n: 320,
  correct: 310,
  cannot_judge: 30,
  precision: 310 / 320,
  wilson_low: 0.9435,
  wilson_high: 0.983,
  criterion_met: true,
  reviewer_roles: ["clinical_pharmacologist", "pharmacometrician"],
};

const statements = (audit: ExpertAudit | null) => ({
  research_use: "Research use only. Not for clinical decisions.",
  expert_review: "Expert review has not yet been done.",
  experimental: "Experimental: this model kit is an early research preview.",
  expert_audit: audit,
});

// --- builders --------------------------------------------------------------------------------

export function metric(
  name: "auc" | "cmax",
  over: Partial<MetricOut> = {},
): MetricOut {
  return {
    name,
    tested: false,
    n_points: 0,
    n_studies: 0,
    gm_ratio: null,
    gmfe: null,
    within_2_fold_points: 0,
    all_within_2_fold: null,
    ...over,
  };
}

export function point(
  id: string,
  over: Partial<PointOut> & Pick<PointOut, "observed" | "predicted">,
): PointOut {
  return {
    evidence_id: id,
    metric: "auc",
    study_id: "NCT00000001",
    dose_mg: 10,
    ratio: over.predicted / over.observed,
    within_2_fold: true,
    rebuilt_without_study: false,
    ...over,
  };
}

export function evidenceRow(
  id: string,
  over: Partial<EvidenceRow> = {},
): EvidenceRow {
  return {
    id,
    analyte: "synthetic",
    analyte_class: "parent",
    parameter: "cl",
    value: 10,
    value_low: null,
    value_high: null,
    statistic: "mean",
    unit: "L/h",
    value_si: 10,
    dose: 10,
    route: "iv",
    regimen: "single",
    interval_h: null,
    population: "healthy adults",
    n_subjects: 12,
    formulation: "immediate_release",
    coadministered: false,
    study_id: "NCT00000001",
    source_id: "clinicaltrials_gov",
    source_locator: `NCT00000001#outcome-1/${id}`,
    source_version: "record last updated 2020-01-01; retrieved 2026-01-01",
    source_url: "https://clinicaltrials.gov/study/NCT00000001",
    quote: `Synthetic outcome ${id} | group: 10 mg single dose | value 10 L/h (MEAN)`,
    reader_a: "agree",
    reader_b: "agree",
    confirmed: true,
    confirm_reason: "both annotation passes judged the extracted value correct",
    note: null,
    extracted_at: "2026-01-01",
    role: "building",
    reason: null,
    origin: "synthetic",
    derivation: null,
    arm_id: null,
    food: "unspecified",
    evidence_kind: "pk",
    dispersion_type: "none",
    dispersion_low: null,
    dispersion_high: null,
    ...over,
  };
}

function param(
  name: string,
  value: number,
  unit: string,
  evidenceId: string,
  over: Partial<ParamOut> = {},
): ParamOut {
  return {
    name,
    label: name.toUpperCase(),
    value,
    unit,
    confidence_class: "B",
    n_studies: 1,
    between_study_cv: null,
    derivation: null,
    notes: [],
    evidence_ids: [evidenceId],
    ...over,
  };
}

const interval = (
  m: "auc" | "cmax",
  over: Partial<IntervalOut> = {},
): IntervalOut => ({
  metric: m,
  shown: false,
  n_studies: 2,
  min_studies: 20,
  coverage: 0.8,
  fold_half: null,
  reason: "interval_n_too_small",
  ...over,
});

const NO_SP = {
  statements: [] as SpecialStatement[],
  atlas: [] as SpecialAtlas[],
  notes: ["sp_none"],
};

export function spStatement(
  i: number,
  over: Partial<SpecialStatement> = {},
): SpecialStatement {
  const setId = `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`;
  return {
    pop_class: "renal",
    grade: "severe",
    measure: "auc",
    ratio: 2.1,
    ratio_text: "about 2.1-fold",
    definition: "creatinine clearance below 30 mL/min",
    reference: "creatinine clearance above 80 mL/min",
    quote: `Synthetic label sentence ${i}: exposure was about 2.1 times higher in the group than in the reference group.`,
    set_id: setId,
    version: String(i),
    effective_date: "2025-01-01",
    section: "12.3",
    n_labels: 3,
    from_table: false,
    source_url: `https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=${setId}`,
    status: "two_readers_agree",
    ...over,
  };
}

export function spAtlas(
  i: number,
  over: Partial<SpecialAtlas> = {},
): SpecialAtlas {
  const setId = `11111111-1111-4111-8111-${String(i).padStart(12, "0")}`;
  return {
    measure: "cl",
    ratio: 0.56,
    qualitative: false,
    quote: `Synthetic atlas sentence ${i}: apparent clearance decreased as age increased.`,
    set_id: setId,
    version: "1",
    n_labels: 5,
    quote_checked: true,
    source_url: `https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=${setId}`,
    status: "automated_extraction_unconfirmed",
    ...over,
  };
}

function summaryOf(
  key: string,
  name: string,
  status: Status,
  over: Partial<DrugSummary> = {},
): DrugSummary {
  return {
    key,
    name,
    status,
    status_reasons: ["no_parameter_set"],
    has_set: false,
    set_complete: false,
    basis: null,
    rows: 6,
    confirmed_rows: 4,
    studies: 2,
    auc: metric("auc"),
    cmax: metric("cmax"),
    exportable: false,
    experimental: true,
    ...over,
  };
}

interface Built {
  out: DrugOut;
  evidence: EvidenceOut;
}

function build(
  audit: ExpertAudit | null,
  summary: DrugSummary,
  over: Partial<DrugOut>,
  rows: EvidenceRow[],
): Built {
  const metrics = [summary.auc, summary.cmax];
  const base: DrugOut = {
    release: RELEASE,
    statements: statements(audit),
    summary,
    parameter_set: null,
    no_set_reasons: [],
    validation: {
      status: summary.status,
      design: "leave_one_study_out",
      reasons: summary.status_reasons,
      metrics,
      points: [],
      excluded: [],
      suspect: [],
      failed_point_ids: [],
      interval_reason: "interval_n_too_small",
      interval_min_studies: 20,
      interval_n_studies: 0,
      band: [0.5, 2],
      unit_note:
        "ratio = predicted / observed; AUC to infinity in ng*h/mL, Cmax in ng/mL",
    },
    intervals: [interval("auc"), interval("cmax")],
    targets: [],
    special_populations: NO_SP,
    reason_text: {},
    ...over,
  };
  return {
    out: checked(drugOut, base, `drug ${summary.key}`),
    evidence: checked(
      evidenceOut,
      {
        release: RELEASE,
        statements: statements(audit),
        drug: summary.key,
        rows,
        attribution: [
          "ClinicalTrials.gov: source of the data is ClinicalTrials.gov; units were converted and rows filtered (modifications by Janus).",
          "DailyMed labels: public domain (U.S. government work).",
        ],
        reason_text: {},
      },
      `evidence ${summary.key}`,
    ),
  };
}

const TARGETS = ["janus", "mrgsolve", "pksim"] as const;

function ertugliflozin(audit: ExpertAudit | null): Built {
  const points = [
    point("ev_ert_v1", { metric: "auc", observed: 1636, predicted: 1339 }),
    point("ev_ert_v2", {
      metric: "auc",
      study_id: "PMC0000002",
      observed: 1334,
      predicted: 1339,
    }),
    point("ev_ert_v3", { metric: "cmax", observed: 150, predicted: 90 }),
  ];
  const summary = summaryOf("ertugliflozin", "Ertugliflozin", "validated", {
    status_reasons: ["all_points_within_2_fold"],
    has_set: true,
    set_complete: true,
    basis: "iv",
    rows: 14,
    confirmed_rows: 13,
    studies: 4,
    auc: metric("auc", {
      tested: true,
      n_points: 2,
      n_studies: 2,
      gm_ratio: 0.9,
      gmfe: 1.1,
      within_2_fold_points: 2,
      all_within_2_fold: true,
    }),
    cmax: metric("cmax", {
      tested: true,
      n_points: 1,
      n_studies: 1,
      gm_ratio: 0.6,
      gmfe: 1.67,
      within_2_fold_points: 1,
      all_within_2_fold: true,
    }),
    exportable: true,
  });
  return build(
    audit,
    summary,
    {
      parameter_set: {
        model: "one_compartment",
        model_reason: "no_central_volume_evidence",
        basis: "iv",
        apparent: false,
        complete: true,
        missing: [],
        warnings: ["half_life_inconsistent"],
        implied_half_life_h: 5.29,
        stated_half_life_h: 16.09,
        params: [
          param("cl", 11.2, "L/h", "ev_ert_cl", { confidence_class: "A" }),
          param("v", 85.5, "L", "ev_ert_v"),
        ],
        left_out: [{ evidence_id: "ev_ert_x1", reason: "not_confirmed" }],
        held_out_studies: ["clinicaltrials_gov:NCT00000001"],
      },
      validation: {
        status: "validated",
        design: "leave_one_study_out",
        reasons: ["all_points_within_2_fold"],
        metrics: [summary.auc, summary.cmax],
        points,
        excluded: [
          {
            evidence_id: "ev_ert_x2",
            reason: "auc_to_last_sampling_time_not_comparable",
          },
        ],
        suspect: [],
        failed_point_ids: [],
        interval_reason: "interval_n_too_small",
        interval_min_studies: 20,
        interval_n_studies: 2,
        band: [0.5, 2],
        unit_note:
          "ratio = predicted / observed; AUC to infinity in ng*h/mL, Cmax in ng/mL",
      },
      targets: [...TARGETS],
    },
    [
      evidenceRow("ev_ert_cl", {
        analyte: "ertugliflozin",
        parameter: "cl",
        value: 11.2,
        value_si: 11.2,
        quote:
          "Total body clearance | group: ertugliflozin 15 mg intravenous | value 11.2 L/h (MEAN)",
        source_locator: "NCT00000001#outcome-3/OG000",
        source_url: "https://clinicaltrials.gov/study/NCT00000001",
        confirm_reason:
          "both annotation passes judged the extracted value correct",
      }),
      evidenceRow("ev_ert_v", {
        parameter: "vss",
        value: 85.5,
        value_si: 85.5,
        unit: "L",
      }),
      ...points.map((p) =>
        evidenceRow(p.evidence_id, {
          parameter: p.metric === "auc" ? "auc_inf" : "cmax",
          value: p.observed,
          value_si: p.observed,
          unit: p.metric === "auc" ? "ng*h/mL" : "ng/mL",
          route: "oral",
          study_id: p.study_id,
          role: "validation",
        }),
      ),
      evidenceRow("ev_ert_x1", {
        confirmed: false,
        reader_b: "disagree",
        role: "excluded",
        reason: "not_confirmed",
      }),
    ],
  );
}

function sunitinib(audit: ExpertAudit | null): Built {
  const points = [
    point("ev_sun_v1", { metric: "auc", observed: 1000, predicted: 806 }),
    point("ev_sun_v2", { metric: "cmax", observed: 40, predicted: 36 }),
    point("ev_sun_v3", {
      metric: "cmax",
      observed: 40,
      predicted: 15,
      within_2_fold: false,
    }),
  ];
  const summary = summaryOf("sunitinib", "Sunitinib", "failed", {
    status_reasons: ["point_outside_2_fold"],
    has_set: true,
    set_complete: true,
    basis: "oral_apparent",
    rows: 9,
    confirmed_rows: 8,
    studies: 3,
    auc: metric("auc", {
      tested: true,
      n_points: 1,
      n_studies: 1,
      gm_ratio: 0.8,
      gmfe: 1.24,
      within_2_fold_points: 1,
      all_within_2_fold: true,
    }),
    cmax: metric("cmax", {
      tested: true,
      n_points: 2,
      n_studies: 1,
      gm_ratio: 0.5,
      gmfe: 1.98,
      within_2_fold_points: 1,
      all_within_2_fold: false,
    }),
    exportable: true,
  });
  return build(
    audit,
    summary,
    {
      parameter_set: {
        model: "one_compartment",
        model_reason: "no_central_volume_evidence",
        basis: "oral_apparent",
        apparent: true,
        complete: true,
        missing: [],
        warnings: [],
        implied_half_life_h: null,
        stated_half_life_h: null,
        params: [
          param("cl", 35, "L/h", "ev_sun_cl", { confidence_class: "C" }),
          param("v", 2200, "L", "ev_sun_v"),
          param("f", 1, "", "ev_sun_f", { derivation: "f_fixed_apparent" }),
          param("ka", 0.9, "1/h", "ev_sun_ka", { derivation: "ka_from_tmax" }),
        ],
        left_out: [],
        held_out_studies: ["drugsatfda_review:FDA review SYNTHETIC0001"],
      },
      validation: {
        status: "failed",
        design: "leave_one_study_out",
        reasons: ["point_outside_2_fold"],
        metrics: [summary.auc, summary.cmax],
        points,
        excluded: [],
        suspect: ["absorption_rate_or_volume"],
        failed_point_ids: ["ev_sun_v3"],
        interval_reason: "interval_n_too_small",
        interval_min_studies: 20,
        interval_n_studies: 1,
        band: [0.5, 2],
        unit_note:
          "ratio = predicted / observed; AUC to infinity in ng*h/mL, Cmax in ng/mL",
      },
      targets: [...TARGETS],
    },
    [
      evidenceRow("ev_sun_cl", { parameter: "cl_f", route: "oral" }),
      evidenceRow("ev_sun_v", { parameter: "v_f", route: "oral", unit: "L" }),
      evidenceRow("ev_sun_f", { parameter: "f", route: "oral", unit: "" }),
      evidenceRow("ev_sun_ka", { parameter: "tmax", route: "oral", unit: "h" }),
    ],
  );
}

function dolutegravir(audit: ExpertAudit | null): Built {
  const summary = summaryOf("dolutegravir", "Dolutegravir", "not_validated", {
    status_reasons: ["cmax_not_tested"],
    has_set: true,
    set_complete: true,
    basis: "oral_apparent",
    rows: 10,
    confirmed_rows: 9,
    studies: 4,
    auc: metric("auc", {
      tested: true,
      n_points: 1,
      n_studies: 1,
      gm_ratio: 0.73,
      gmfe: 1.36,
      within_2_fold_points: 1,
      all_within_2_fold: true,
    }),
    exportable: true,
  });
  return build(
    audit,
    summary,
    {
      parameter_set: {
        model: "one_compartment",
        model_reason: "no_central_volume_evidence",
        basis: "oral_apparent",
        apparent: true,
        complete: true,
        missing: [],
        warnings: [],
        implied_half_life_h: null,
        stated_half_life_h: null,
        params: [
          param("cl", 1.0, "L/h", "ev_dtg_cl"),
          param("v", 17, "L", "ev_dtg_v"),
        ],
        left_out: [],
        held_out_studies: [],
      },
      validation: {
        status: "not_validated",
        design: "leave_one_study_out",
        reasons: ["cmax_not_tested"],
        metrics: [summary.auc, summary.cmax],
        points: [
          point("ev_dtg_v1", {
            metric: "auc",
            observed: 5000,
            predicted: 3660,
          }),
        ],
        excluded: [],
        suspect: [],
        failed_point_ids: [],
        interval_reason: "interval_n_too_small",
        interval_min_studies: 20,
        interval_n_studies: 1,
        band: [0.5, 2],
        unit_note:
          "ratio = predicted / observed; AUC to infinity in ng*h/mL, Cmax in ng/mL",
      },
      targets: [...TARGETS],
    },
    [
      evidenceRow("ev_dtg_cl", { parameter: "cl_f", route: "oral" }),
      evidenceRow("ev_dtg_v", { parameter: "v_f", route: "oral", unit: "L" }),
    ],
  );
}

function gabapentin(audit: ExpertAudit | null): Built {
  const summary = summaryOf("gabapentin", "Gabapentin", "not_validated", {
    status_reasons: ["no_parameter_set", "no_confirmed_clearance"],
    rows: 12,
    confirmed_rows: 8,
  });
  return build(
    audit,
    summary,
    {
      no_set_reasons: ["no_confirmed_clearance", "iv_evidence_incomplete"],
      special_populations: {
        statements: [],
        atlas: [spAtlas(9)],
        notes: ["sp_atlas_note"],
      },
    },
    [
      evidenceRow("ev_gab_1", {
        parameter: "auc_last",
        value: 41848.88,
        value_si: 41848.88,
        unit: "ng*h/mL",
        route: "oral",
        role: "excluded",
        reason: "held_out_study",
      }),
      evidenceRow("ev_gab_2", {
        parameter: "cmax",
        unit: "ng/mL",
        route: "oral",
        role: "excluded",
        reason: "not_confirmed",
        confirmed: false,
      }),
    ],
  );
}

/** A set with a validation point on the 2-fold edge and 24 excluded rows (the long table). */
function repaglinide(audit: ExpertAudit | null): Built {
  const points = [
    point("ev_rep_v1", { metric: "auc", observed: 100, predicted: 200 }),
    point("ev_rep_v2", {
      metric: "auc",
      study_id: "PMC0000009",
      observed: 100,
      predicted: 60,
    }),
  ];
  const summary = summaryOf("repaglinide", "Repaglinide", "not_validated", {
    status_reasons: ["cmax_not_tested"],
    has_set: true,
    set_complete: true,
    basis: "oral_apparent",
    studies: 3,
    auc: metric("auc", {
      tested: true,
      n_points: 2,
      n_studies: 2,
      gm_ratio: 1.1,
      gmfe: 1.6,
      within_2_fold_points: 2,
      all_within_2_fold: true,
    }),
    exportable: true,
  });
  const excluded = Array.from({ length: 24 }, (_, i) =>
    evidenceRow(`ev_rep_x${i}`, {
      parameter: "cmax",
      unit: "ng/mL",
      route: "oral",
      role: "excluded",
      reason: "held_out_study",
    }),
  );
  return build(
    audit,
    summary,
    {
      parameter_set: {
        model: "two_compartment",
        model_reason: "two_volumes_differ",
        basis: "oral_apparent",
        apparent: true,
        complete: true,
        missing: [],
        warnings: [],
        implied_half_life_h: null,
        stated_half_life_h: null,
        params: [
          param("cl", 38, "L/h", "ev_rep_cl", {
            n_studies: 2,
            between_study_cv: 0.2,
          }),
          param("v", 31, "L", "ev_rep_v"),
        ],
        left_out: [],
        held_out_studies: [],
      },
      validation: {
        status: "not_validated",
        design: "leave_one_study_out",
        reasons: ["cmax_not_tested"],
        metrics: [summary.auc, summary.cmax],
        points,
        excluded: [],
        suspect: [],
        failed_point_ids: [],
        interval_reason: "interval_n_too_small",
        interval_min_studies: 20,
        interval_n_studies: 2,
        band: [0.5, 2],
        unit_note:
          "ratio = predicted / observed; AUC to infinity in ng*h/mL, Cmax in ng/mL",
      },
      targets: [...TARGETS],
    },
    [
      evidenceRow("ev_rep_cl", { parameter: "cl_f", route: "oral" }),
      evidenceRow("ev_rep_v", { parameter: "v_f", route: "oral", unit: "L" }),
      ...excluded,
    ],
  );
}

const SP_GRADE_PLAN: [SpecialStatement["pop_class"], string][] = [
  ["geriatric", "age65"],
  ["geriatric", "age75"],
  ["renal", "mild"],
  ["renal", "moderate"],
  ["renal", "severe"],
  ["hepatic", "cp_a"],
  ["hepatic", "cp_b"],
  ["hepatic", "cp_c"],
];

function withStatements(
  audit: ExpertAudit | null,
  key: string,
  name: string,
  n: number,
  atlas: SpecialAtlas[],
): Built {
  return build(
    audit,
    summaryOf(key, name, "not_validated"),
    {
      no_set_reasons: ["no_confirmed_clearance"],
      special_populations: {
        statements: SP_GRADE_PLAN.slice(0, n).map(([pop_class, grade], i) =>
          spStatement(i + 1, { pop_class, grade }),
        ),
        atlas,
        notes: atlas.length
          ? ["sp_statements_note", "sp_atlas_note"]
          : ["sp_statements_note"],
      },
    },
    [evidenceRow(`ev_${key}_1`, { role: "excluded", reason: "not_confirmed" })],
  );
}

const FILLERS = Array.from({ length: 22 }, (_, i) => {
  const n = String(i + 1).padStart(2, "0");
  return { key: `filler_${n}`, name: `Filler ${n}` };
});

// --- the whole set ---------------------------------------------------------------------------

export interface ModelKitSet {
  /** The list answer, with every drug of the set. */
  drugs: DrugsOut;
  validation: SystemOut;
  drug: Record<string, DrugOut>;
  evidence: Record<string, EvidenceOut>;
  /** The same answers as raw JSON, the shape of a recorded file (`demoModelKit` input). */
  raw: ModelKitFixture;
}

/** Named drugs, for the tests that need one of each kind. */
export const KEYS = {
  validated: "ertugliflozin",
  failed: "sunitinib",
  notValidated: "dolutegravir",
  noSet: "gabapentin",
  /** Set, a point on the 2-fold edge, 24 excluded evidence rows. */
  longEvidence: "repaglinide",
  /** Eight special-population statements and two atlas rows. */
  manyStatements: "metformin",
  /** Three statements, no atlas row. */
  fewStatements: "amlodipine",
} as const;

export function modelKitSet(audit: ExpertAudit | null = null): ModelKitSet {
  const built: Built[] = [
    ertugliflozin(audit),
    sunitinib(audit),
    dolutegravir(audit),
    gabapentin(audit),
    repaglinide(audit),
    withStatements(audit, "metformin", "Metformin", 8, [
      spAtlas(1),
      spAtlas(2),
    ]),
    withStatements(audit, "amlodipine", "Amlodipine", 3, []),
    ...FILLERS.map((f) =>
      build(audit, summaryOf(f.key, f.name, "not_validated"), {}, []),
    ),
  ];
  const summaries = built.map((b) => b.out.summary);
  const count = (s: Status) => summaries.filter((x) => x.status === s).length;
  const drugs = checked(
    drugsOut,
    {
      release: RELEASE,
      statements: statements(audit),
      drugs: summaries,
      total: summaries.length,
      offset: 0,
      limit: summaries.length,
      counts: {
        all: summaries.length,
        with_set: summaries.filter((s) => s.has_set).length,
        validated: count("validated"),
        not_validated: count("not_validated"),
        failed: count("failed"),
      },
    },
    "drugs",
  );
  const validation = report(audit, summaries);
  const drug = Object.fromEntries(built.map((b) => [b.out.summary.key, b.out]));
  const evidence = Object.fromEntries(
    built.map((b) => [b.out.summary.key, b.evidence]),
  );
  return {
    drugs,
    validation,
    drug,
    evidence,
    raw: { recorded: "synthetic", drugs, validation, drug, evidence },
  };
}

function report(audit: ExpertAudit | null, all: DrugSummary[]): SystemOut {
  const by = (s: Status) => all.filter((d) => d.status === s).length;
  const iv = (
    m: "auc" | "cmax",
    over: Partial<IntervalOut> = {},
  ): IntervalOut => interval(m, { n_studies: 7, ...over });
  return checked(
    systemOut,
    {
      release: RELEASE,
      statements: statements(audit),
      n_drugs: all.length,
      by_status: {
        validated: by("validated"),
        not_validated: by("not_validated"),
        failed: by("failed"),
      },
      metrics: [
        {
          name: "auc",
          n_drugs: 3,
          gmfe: 1.3,
          within_2_fold: 3,
          within_2_fold_share: 1,
          wilson_low: 0.44,
          wilson_high: 1,
          n_points: 11,
          points_within_2_fold: 11,
          points_gmfe: 1.2,
        },
        {
          name: "cmax",
          n_drugs: 0,
          gmfe: null,
          within_2_fold: 0,
          within_2_fold_share: null,
          wilson_low: null,
          wilson_high: null,
          n_points: 0,
          points_within_2_fold: 0,
          points_gmfe: null,
        },
      ],
      n_studies: 7,
      interpretable: false,
      min_drugs_for_interpretation: 10,
      n_drugs_both_tested: 4,
      conformal: "interval_n_too_small",
      // one metric with an interval, one without, so both report texts are covered
      intervals: [
        iv("auc", {
          shown: true,
          n_studies: 25,
          fold_half: 2.1,
          reason: null,
        }),
        iv("cmax"),
      ],
      n_with_set: all.filter((d) => d.has_set).length,
      n_complete_set: all.filter((d) => d.set_complete).length,
      rows_total: 812,
      rows_confirmed: 474,
      confirmed_parent_rows: 449,
      formulation_counts: {
        fixed_dose_combination: 2,
        immediate_release: 308,
        modified_release: 1,
        solution: 59,
        unspecified: 79,
      },
      route_counts: { iv: 46, oral: 387, unknown: 16 },
      not_validated_reasons: { cmax_not_tested: 3, no_parameter_set: 20 },
      no_set_reasons: { no_confirmed_clearance: 20 },
      precision: {
        measured_on: "2026-01-02",
        n: 126,
        correct: 125,
        share: 125 / 126,
        wilson_low: 0.9564,
        wilson_high: 0.9986,
        n_conservative: 126,
        share_conservative: 125 / 126,
        wilson_low_conservative: 0.9564,
        wilson_high_conservative: 0.9986,
        formulation_n: 122,
        formulation_correct: 121,
        formulation_share: 121 / 122,
        formulation_wilson_low: 0.955,
        formulation_wilson_high: 0.9986,
        target: 0.9,
      },
      document_sources: [
        {
          source_id: "drugsatfda_review",
          published: false,
          rows: 0,
          confirmed_rows: 0,
          held_back_rows: 290,
          measured_on: "2026-01-02",
          n: 92,
          correct: 44,
          share: 44 / 92,
          wilson_low: 0.379,
          wilson_high: 0.579,
          n_conservative: 100,
          share_conservative: 0.44,
        },
        {
          source_id: "pmc_oa",
          published: true,
          rows: 12,
          confirmed_rows: 10,
          held_back_rows: 0,
          measured_on: "2026-01-02",
          n: 91,
          correct: 88,
          share: 88 / 91,
          wilson_low: 0.91,
          wilson_high: 0.99,
          n_conservative: 91,
          share_conservative: 88 / 91,
        },
      ],
      study_identity: {
        groups_with_several_studies: 21,
        links: { code: 7, numeric_duplicate: 15 },
        test_studies_without_rule: 299,
        test_studies: 288,
      },
      special_populations: {
        drugs: 151,
        statements: 389,
        by_class: { geriatric: 70, renal: 146, hepatic: 173 },
        drugs_by_class: { geriatric: 41, renal: 66, hepatic: 75 },
        atlas_drugs: 64,
        atlas_rows: 64,
        coverage: {
          labels_read: 2645,
          labels_matched: 207,
          drugs_with_a_matched_label: 602,
          labels_with_a_candidate: 60,
          candidate_pairs: 188,
          confirmed_pairs: 60,
          confirmed_pairs_displayed: 56,
          drugs_with_a_displayed_statement: 151,
        },
        precision: {
          measured_on: "2026-01-02",
          n: 88,
          correct: 57,
          share: 57 / 88,
          wilson_low: 0.54,
          wilson_high: 0.74,
          n_conservative: 90,
          share_conservative: 0.63,
          wilson_low_conservative: 0.53,
          wilson_high_conservative: 0.73,
          target: 0.9,
        },
      },
      missing: ["gate_not_interpretable", "expert_review_pending"],
      caveats: ["n_very_small", "two_automated_passes"],
      reason_text: {},
    },
    "report",
  );
}

/** Every reason code that occurs in the answers of a set (for the glossary check). */
export function reasonCodesOf(s: ModelKitSet): Set<string> {
  const seen = new Set<string>();
  const add = (x: unknown): void => {
    if (typeof x === "string") seen.add(x);
    else if (Array.isArray(x)) x.forEach(add);
  };
  for (const d of Object.values(s.drug)) {
    add(d.summary.status_reasons);
    add(d.no_set_reasons);
    add(d.validation.reasons);
    add(d.validation.suspect);
    add(d.validation.interval_reason);
    add(d.validation.excluded.map((e) => e.reason));
    add(d.intervals.map((i) => i.reason));
    add(d.special_populations.notes);
    const ps = d.parameter_set;
    if (ps) {
      add(ps.model_reason);
      add(ps.warnings);
      add(ps.missing);
      add(ps.left_out.map((e) => e.reason));
      for (const p of ps.params) {
        add(p.derivation);
        add(p.notes);
      }
    }
  }
  add(s.validation.conformal);
  add(s.validation.caveats);
  add(s.validation.missing);
  for (const e of Object.values(s.evidence)) add(e.rows.map((r) => r.reason));
  return seen;
}

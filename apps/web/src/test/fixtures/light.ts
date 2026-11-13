/**
 * Synthetic light-face answers (overview, hypothesis cards per goal, validation, export) for the
 * behaviour tests. Typed with the production types and decoded by the production decoders;
 * nothing is read from the recorded file.
 *
 * Goals: alopecia (14 cards, so "show more" has something to show, with tied ranks), erectile
 * dysfunction (one label card) and multiple myeloma (a card with only an inverse FAERS signal,
 * "reported less often than expected"). The validation set has 13 cases: two informative hits,
 * one hit that is not informative, eight misses and two not evaluable.
 */
import * as D from "@/api/decode";
import {
  cardsOut,
  exportOut,
  overviewOut,
  validationOut,
  type Card,
  type CardsOut,
  type CaseResult,
  type ExportOut,
  type ExportRow,
  type GoalSummary,
  type OverviewOut,
  type Source,
  type ValidationOut,
} from "@/light/model";

function checked<T>(decoder: D.Decoder<T>, value: T, what: string): T {
  const r = D.decode(decoder, value);
  if (!r.ok) throw new Error(`synthetic fixture ${what} does not decode`);
  return value;
}

const labels = (en: string) => ({
  en,
  tr: `${en} (tr)`,
  de: `${en} (de)`,
  fr: `${en} (fr)`,
  es: `${en} (es)`,
});

const SNAPSHOT = {
  build_id: "synthetic0000000",
  onsides_release: "vtest",
  onsides_date: "2026-01-01",
  faers_snapshot_date: "2026-01-01",
  faers_window: ["2025Q4", "2026Q1"],
  openfda_date: "2026-01-01",
};
const common = {
  status: "prototype" as const,
  // the contract's only value of this field
  review_status: "automated_checks_pending_expert" as const,
  snapshot: SNAPSHOT,
  codes: ["prototype", "candidate_not_treatment"],
  disclaimer:
    "Janus provides information, not medical advice. Research prototype — not a medical device.",
  attribution: ["Synthetic test data, CC BY 4.0."],
};

export const GOALS = {
  alopecia: "Hair loss (alopecia)",
  erectile_dysfunction: "Erectile dysfunction",
  multiple_myeloma: "Multiple myeloma",
} as const;
export type GoalKey = keyof typeof GOALS;

const goalRef = (key: GoalKey) => ({ key, labels: labels(GOALS[key]) });
const goalSummary = (key: GoalKey, candidates: number): GoalSummary => ({
  key,
  labels: labels(GOALS[key]),
  candidates,
  label_terms: ["Synthetic term"],
  faers_pts: ["Synthetic PT"],
  benefit_keys: [],
  inverse_tested: 100,
  inverse_found: 12,
  inverse_expected_by_chance: 2.5,
});

const SOURCES: Source[] = [
  {
    id: "dataset:onsides",
    title: "Synthetic side-effect dataset",
    doi: null,
    url: "https://example.org/onsides",
    status: "no_doi",
    snapshot_date: "2026-01-01",
  },
  {
    id: "dataset:faers",
    title: "Synthetic reports dataset",
    doi: null,
    url: "https://example.org/faers",
    status: "no_doi",
    snapshot_date: "2026-01-01",
  },
  {
    id: "paper:synthetic_2011:a",
    title: "A synthetic paper on side effects",
    doi: "10.0000/synthetic.a",
    url: "https://doi.org/10.0000/synthetic.a",
    status: "ok",
    snapshot_date: "2026-01-01",
  },
];

const ingredient = (key: string, en: string) => ({
  key,
  labels: labels(en),
});

const stats = (ror: number, low: number, high: number) => {
  const est = {
    prr: ror,
    ror,
    ror_ci: { low, high, level: 0.95, method: "woolf_log" },
    chi2: 5,
    chi2_form: "yates",
  };
  const cells = { a: 55, b: 42885, c: 2279, d: 1236534, n: 1281753 };
  return {
    region: "ALL" as const,
    scope: "any" as const,
    cells,
    haldane_applied: false,
    estimates: est,
    evans_met: false,
    ror_signal: false,
    assessment: "not_disproportionate" as const,
    sensitivity: {
      cells,
      haldane_applied: false,
      estimates: est,
      assessment: "not_disproportionate" as const,
      differs: false,
    },
    denominator_sensitive: false,
    codes: [],
  };
};

/** A card with a label-effect signal at the given (possibly tied) rank. */
export function labelCard(
  goal: GoalKey,
  key: string,
  name: string,
  best: number,
  worst: number,
  population: number,
): Card {
  return {
    ingredient: ingredient(key, name),
    goal: goalRef(goal),
    rank: { best, worst, population },
    signals: [
      {
        type: "label_effect",
        label: {
          regions: ["US", "UK"],
          labels_with_effect: 29,
          labels_total: 32,
          share_low: 0.76,
          sections: ["AR", "NA"],
          terms: ["Synthetic term"],
          evidence_ids: ["dataset:onsides", "paper:synthetic_2011:a"],
          nonspecific: false,
        },
        inverse: null,
        patient: null,
        codes: ["label_effect_meaning", "label_extraction_limits"],
      },
    ],
    sources: SOURCES,
    removed_sources: [],
    codes: ["candidate_not_treatment"],
  };
}

/** A card that has only an inverse FAERS signal (the drug is reported less often than expected). */
export function inverseCard(
  goal: GoalKey,
  key: string,
  name: string,
  rank: number,
  population: number,
): Card {
  return {
    ...labelCard(goal, key, name, rank, rank, population),
    signals: [
      {
        type: "inverse_faers",
        label: null,
        inverse: {
          stats: stats(0.7, 0.53, 0.91),
          pts: ["Synthetic PT"],
          reports: 55,
          expected: 78.2,
          observed_over_expected: 0.7,
          upper_bound_sensitive: false,
          evidence_ids: ["dataset:faers"],
          locator: "faers:ingredient=Q1;event=;region=ALL;scope=any",
        },
        patient: null,
        codes: ["inverse_meaning", "inverse_reporting_bias"],
      },
    ],
  };
}

function cardsAnswer(goal: GoalKey, cards: Card[], total: number): CardsOut {
  return checked(
    cardsOut,
    {
      ...common,
      goal: goalRef(goal),
      total,
      offset: 0,
      cards,
      patient_reported: [],
      patient_layer: "layer_unavailable",
      removed_by_integrity: 0,
      warning_sources: [],
    },
    `cards ${goal}`,
  );
}

const ALOPECIA_POPULATION = 142;

function alopeciaCards(): Card[] {
  const rows: [number, number][] = [
    [1, 1],
    [2, 2],
    [3, 5], // three ingredients share ranks 3 to 5
    [3, 5],
    [3, 5],
    ...Array.from({ length: 9 }, (_, i): [number, number] => [6 + i, 6 + i]),
  ];
  return rows.map(([best, worst], i) =>
    labelCard(
      "alopecia",
      `Q${5000 + i}`,
      i === 0 ? "minoxidil" : `synthetic ingredient ${i}`,
      best,
      worst,
      ALOPECIA_POPULATION,
    ),
  );
}

export interface LightSet {
  overview: OverviewOut;
  cards: Record<GoalKey, CardsOut>;
  validation: ValidationOut;
  export: ExportOut;
}

const runOf = (
  run: "primary" | "primary_indication" | "primary_strict" | "sensitivity",
  over: Partial<CaseResult["primary"]> = {},
): CaseResult["primary"] => ({
  run,
  rank: null,
  population: 20,
  hit: false,
  informative: true,
  labels_used: 3,
  labels_removed_indication: 0,
  labels_removed_not_in_openfda: 0,
  signal_types: [],
  reason: "no_label_mapping",
  chance_hit: 0.5,
  percentile: null,
  ...over,
});

type Outcome = "informative_hit" | "plain_hit" | "miss" | "not_evaluable";

function caseOf(
  id: string,
  ingredientKey: string,
  ingredientName: string,
  goal: GoalKey | "parkinsons_disease",
  outcome: Outcome,
): CaseResult {
  const hit = outcome === "informative_hit" || outcome === "plain_hit";
  const over: Partial<CaseResult["primary"]> = {
    hit,
    informative: outcome !== "plain_hit" && outcome !== "not_evaluable",
    rank: hit ? { best: 1, worst: 1, population: 20 } : null,
    reason: hit
      ? "hit"
      : outcome === "not_evaluable"
        ? "not_evaluable"
        : "no_label_mapping",
    signal_types: hit ? ["label_effect"] : [],
    percentile: hit ? 0.95 : null,
  };
  return {
    case: {
      id,
      ingredient_name: ingredientName,
      ingredient_key: ingredientKey,
      goal,
      original_use: "a synthetic original use",
      later_year: 1999,
      evidence_ids: ["paper:synthetic_2011:a"],
      note: "A synthetic note for this case.",
    },
    primary: runOf("primary", over),
    primary_indication: runOf("primary_indication", over),
    primary_strict: runOf("primary_strict", over),
    sensitivity: runOf("sensitivity", over),
    faers: null,
    faers_inverse: false,
    faers_includes_later_use: false,
  };
}

function validationAnswer(): ValidationOut {
  const plan: [string, string, GoalKey | "parkinsons_disease", Outcome][] = [
    ["Q424165", "minoxidil", "alopecia", "informative_hit"],
    ["Q191521", "sildenafil", "erectile_dysfunction", "informative_hit"],
    ["Q2393348", "bimatoprost", "alopecia", "plain_hit"],
    ["Q203174", "thalidomide", "multiple_myeloma", "miss"],
    ["Q409761", "amantadine", "parkinsons_disease", "miss"],
    ["Q424167", "finasteride", "alopecia", "miss"],
    ["Q221174", "topiramate", "alopecia", "miss"],
    ["Q2526479", "liraglutide", "alopecia", "miss"],
    ["Q27261089", "semaglutide", "alopecia", "miss"],
    ["Q411917", "glycopyrrolate", "alopecia", "miss"],
    ["Q71704041", "doxepin", "alopecia", "miss"],
    ["Q900001", "synthetic one", "alopecia", "not_evaluable"],
    ["Q900002", "synthetic two", "alopecia", "not_evaluable"],
  ];
  const cases = plan.map(([k, n, g, o]) =>
    caseOf(`${n.replaceAll(" ", "_")}_case`, k, n, g, o),
  );
  // two informative hits, one hit that is not informative, eight misses, two not evaluable
  const summary = {
    hits: 3,
    informative_hits: 2,
    misses: 8,
    not_evaluable: 2,
    expected_hits_by_chance: 0.37,
  };
  return checked(
    validationOut,
    {
      ...common,
      top_k: 10,
      cases,
      primary: summary,
      sensitivity: summary,
      goals: [
        goalRef("alopecia"),
        goalRef("erectile_dysfunction"),
        goalRef("multiple_myeloma"),
        { key: "parkinsons_disease", labels: labels("Parkinson's disease") },
      ],
      ingredients: Object.fromEntries(plan.map(([k, n]) => [k, labels(n)])),
      sources: SOURCES,
    },
    "validation",
  );
}

function exportRows(cards: Card[]): ExportRow[] {
  return cards.map((c) => {
    const l = c.signals[0]!.label;
    const inv = c.signals[0]!.inverse;
    return {
      goal: c.goal.key,
      ingredient: c.ingredient.key,
      ingredient_name_en: c.ingredient.labels.en!,
      rank_best: c.rank.best,
      rank_worst: c.rank.worst,
      population: c.rank.population,
      signal_types: c.signals.map((s) => s.type),
      label_regions: l?.regions ?? [],
      labels_with_effect: l?.labels_with_effect ?? null,
      labels_total: l?.labels_total ?? null,
      label_terms: l?.terms ?? [],
      faers_reports: inv?.reports ?? null,
      faers_ror: inv?.stats.estimates?.ror ?? null,
      faers_ror_low: inv?.stats.estimates?.ror_ci.low ?? null,
      faers_ror_high: inv?.stats.estimates?.ror_ci.high ?? null,
      patient_reported_released: null,
      source_ids: c.sources.map((s) => s.id),
    };
  });
}

export function lightSet(): LightSet {
  const alopecia = alopeciaCards();
  const ed = [
    labelCard("erectile_dysfunction", "Q191521", "sildenafil", 1, 1, 55),
  ];
  const myeloma = [
    inverseCard("multiple_myeloma", "Q424972", "synthetic inverse drug", 1, 65),
  ];
  const goals = [
    goalSummary("alopecia", ALOPECIA_POPULATION),
    goalSummary("erectile_dysfunction", 55),
    goalSummary("multiple_myeloma", 65),
  ];
  return {
    overview: checked(overviewOut, { ...common, goals, top_k: 10 }, "overview"),
    cards: {
      alopecia: cardsAnswer("alopecia", alopecia, ALOPECIA_POPULATION),
      erectile_dysfunction: cardsAnswer("erectile_dysfunction", ed, 55),
      multiple_myeloma: cardsAnswer("multiple_myeloma", myeloma, 65),
    },
    validation: validationAnswer(),
    export: checked(
      exportOut,
      {
        ...common,
        licence: "CC BY 4.0",
        rows: [
          ...exportRows(alopecia),
          ...exportRows(ed),
          ...exportRows(myeloma),
        ],
        goals,
      },
      "export",
    ),
  };
}

/**
 * Strict decoders for every API response the client reads (experience design §5.2, DP16).
 *
 * Required fields, types, enum values and array bounds are checked; an unknown enum value is a
 * contract error, never a silent default. Unknown extra fields are ignored (forward-compatible
 * reads). A failure throws `ContractError` with the path only (never a value), and the caller
 * shows the generic error without any partial medical content (Req 22.2).
 */

export class ContractError extends Error {
  constructor(readonly path: string) {
    super(`response does not match the contract at ${path}`);
    this.name = "ContractError";
  }
}

export type Decoder<T> = ((value: unknown, path: string) => T) & {
  meta?: Meta;
};
export type Infer<D> = D extends Decoder<infer T> ? T : never;

/** Structure of a decoder, for the mutation tests (P19). Not used at run time. */
export type Meta =
  | { kind: "prim" }
  | { kind: "lit"; values: readonly unknown[] }
  | { kind: "nullable" | "optional"; inner: Decoder<unknown> }
  | { kind: "arr"; inner: Decoder<unknown>; min: number; max: number }
  | { kind: "record"; inner: Decoder<unknown> }
  | { kind: "obj"; shape: Record<string, Decoder<unknown>> }
  | { kind: "tagged"; key: string; members: Record<string, Decoder<unknown>> };

function withMeta<T>(
  d: (value: unknown, path: string) => T,
  meta: Meta,
): Decoder<T> {
  return Object.assign(d, { meta });
}

const fail = (path: string): never => {
  throw new ContractError(path);
};

const PRIM: Meta = { kind: "prim" };
export const str: Decoder<string> = withMeta(
  (v, p) => (typeof v === "string" ? v : fail(p)),
  PRIM,
);
export const num: Decoder<number> = withMeta(
  (v, p) => (typeof v === "number" && Number.isFinite(v) ? v : fail(p)),
  PRIM,
);
export const int: Decoder<number> = withMeta(
  (v, p) => (typeof v === "number" && Number.isInteger(v) ? v : fail(p)),
  PRIM,
);
export const bool: Decoder<boolean> = withMeta(
  (v, p) => (typeof v === "boolean" ? v : fail(p)),
  PRIM,
);

export function lit<const T extends readonly (string | number | boolean)[]>(
  ...values: T
): Decoder<T[number]> {
  return withMeta(
    (v, p) =>
      (values as readonly unknown[]).includes(v) ? (v as T[number]) : fail(p),
    { kind: "lit", values },
  );
}

export function pattern(re: RegExp): Decoder<string> {
  return withMeta(
    (v, p) => (typeof v === "string" && re.test(v) ? v : fail(p)),
    PRIM,
  );
}

export function nullable<T>(d: Decoder<T>): Decoder<T | null> {
  return withMeta((v, p) => (v === null ? null : d(v, p)), {
    kind: "nullable",
    inner: d,
  });
}

type Optional<T> = Decoder<T | null> & { readonly __optional: true };

/** A field the API may omit: absent stays absent (an optional property), null reads as null. */
export function optional<T>(d: Decoder<T>): Optional<T> {
  return withMeta((v, p) => (v === undefined || v === null ? null : d(v, p)), {
    kind: "optional",
    inner: d,
  }) as Optional<T>;
}

export function arr<T>(d: Decoder<T>, min = 0, max = Infinity): Decoder<T[]> {
  return withMeta(
    (v, p) => {
      if (!Array.isArray(v) || v.length < min || v.length > max) return fail(p);
      return v.map((x, i) => d(x, `${p}[${i}]`));
    },
    { kind: "arr", inner: d, min, max },
  );
}

export function record<T>(d: Decoder<T>): Decoder<Record<string, T>> {
  return withMeta(
    (v, p) => {
      if (typeof v !== "object" || v === null || Array.isArray(v))
        return fail(p);
      const out: Record<string, T> = {};
      for (const [k, x] of Object.entries(v)) out[k] = d(x, `${p}.${k}`);
      return out;
    },
    { kind: "record", inner: d },
  );
}

type Shape = Record<string, Decoder<unknown>>;
type OptionalKeys<S> = {
  [K in keyof S]: S[K] extends { readonly __optional: true } ? K : never;
}[keyof S];
export type FromShape<S extends Shape> = {
  [K in Exclude<keyof S, OptionalKeys<S>>]: Infer<S[K]>;
} & {
  [K in OptionalKeys<S>]?: Infer<S[K]>;
};

export function obj<S extends Shape>(shape: S): Decoder<FromShape<S>> {
  return withMeta(
    (v, p) => {
      if (typeof v !== "object" || v === null || Array.isArray(v))
        return fail(p);
      const src = v as Record<string, unknown>;
      const out: Record<string, unknown> = {};
      // An absent field reads as undefined: `optional` accepts it (and keeps it absent), every
      // other decoder fails.
      for (const [k, d] of Object.entries(shape)) {
        if (d.meta?.kind === "optional" && !(k in src)) continue;
        out[k] = d(src[k], `${p}.${k}`);
      }
      return out as FromShape<S>;
    },
    { kind: "obj", shape },
  );
}

/** A union discriminated by a string field. */
export function tagged<
  K extends string,
  M extends Record<string, Decoder<unknown>>,
>(key: K, members: M): Decoder<Infer<M[keyof M]>> {
  return withMeta(
    (v, p) => {
      if (typeof v !== "object" || v === null) return fail(p);
      const tag = (v as Record<string, unknown>)[key];
      const d = typeof tag === "string" ? members[tag] : undefined;
      return d ? (d(v, p) as Infer<M[keyof M]>) : fail(`${p}.${key}`);
    },
    { kind: "tagged", key, members },
  );
}

export type Decoded<T> = { ok: true; value: T } | { ok: false; path: string };

export function decode<T>(d: Decoder<T>, value: unknown): Decoded<T> {
  try {
    return { ok: true, value: d(value, "$") };
  } catch (e) {
    if (e instanceof ContractError) return { ok: false, path: e.path };
    throw e;
  }
}

// --- shared ------------------------------------------------------------------------------------

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
const HEX64 = /^[0-9a-f]{64}$/;
const date = pattern(DATE);
const month = pattern(MONTH);
const hex64 = pattern(HEX64);
const strs = arr(str);

// --- resolution (drug-resolution design §3.2) ---------------------------------------------------

export const sourceRef = obj({
  source_id: str,
  run_id: str,
  region: nullable(str),
  snapshot_date: str,
});

const atcCode = obj({ code: str, source: sourceRef, product: optional(str) });

export const ingredientKey = obj({
  qid: str,
  label_en: nullable(str),
  labels: record(nullable(str)),
});

export const resolvedIngredient = obj({
  position: int,
  published_name: str,
  strength: nullable(str),
  status: lit("mapped", "ambiguous", "unmapped"),
  reason: nullable(
    lit(
      "no_ingredient_key",
      "possible_unsplit_combination",
      "no_ingredient_atc",
      "no_ingredient_atc_for_route",
    ),
  ),
  ingredient_key: nullable(ingredientKey),
  key_candidates: strs,
  match_step: nullable(str),
  atc_codes: arr(atcCode),
  atc_selection: nullable(
    lit(
      "single_ingredient_product",
      "therapeutic_group",
      "anatomical_group",
      "route_group",
      "all_codes",
      "component_code",
    ),
  ),
  rxcuis: strs,
  rxcui_status: nullable(lit("from_wikidata", "not_in_wikidata")),
  source: sourceRef,
  // Additive (medication-passport Req 6.6): Janus's normalised strength, null when unknown.
  strength_code: optional(
    obj({ amount: str, unit: lit("ug", "IU"), basis: lit("unit", "mL", "g") }),
  ),
});

export const productCandidate = obj({
  kind: lit("product"),
  candidate_id: str,
  region: lit("TR", "US", "EU"),
  country: optional(lit("FR", "ES", "IT")),
  matched_by: lit(
    "barcode",
    "ndc_gtin",
    "ndc",
    "name",
    "candidate_id",
    "cip13",
    "ntin",
    "gtin",
    "ai_712",
    "ntin_digits",
  ),
  score: optional(num),
  product_name: nullable(str),
  brand_name: nullable(str),
  generic_name: nullable(str),
  ingredient_text: nullable(str),
  published_atc: nullable(str),
  product_type: nullable(str),
  routes: strs,
  dosage_form: nullable(str),
  marketing_end_date: nullable(str),
  suspension_status: nullable(int),
  name_only: bool,
  homeopathic: bool,
  status_published: strs,
  product_rxcuis: strs,
  packages: arr(obj({ ndc_published: str, ndc11: str })),
  ingredients: arr(resolvedIngredient),
  source: sourceRef,
  // Additive (medication-passport): the dose-form group of the product, for equivalents.
  dose_form_group: optional(str),
});

export const ingredientCandidate = obj({
  kind: lit("ingredient"),
  matched_by: lit("name"),
  score: optional(num),
  ingredient_key: ingredientKey,
  atc_codes: arr(atcCode),
  atc_selection: nullable(lit("all_codes")),
  rxcuis: strs,
  rxcui_status: lit("from_wikidata", "not_in_wikidata"),
  source: sourceRef,
});

export const candidate = tagged("kind", {
  product: productCandidate,
  ingredient: ingredientCandidate,
});

export const resolutionResult = obj({
  dataset_version: hex64,
  regions_searched: arr(lit("TR", "US", "EU")),
  sources: arr(sourceRef),
  scan: optional(
    obj({
      gtin: str,
      expiry: nullable(date),
      expiry_status: lit("absent", "valid", "invalid"),
      serial_present: bool,
      lot_present: bool,
      structural_hint: lit("TR", "US", "FR", "ES", "DE", "other", "none"),
    }),
  ),
  notices: arr(
    obj({
      code: lit(
        "source_may_be_outdated",
        "region_adapter_not_available",
        "unmapped_ingredients",
        "unknown_candidate_ids",
        "no_open_product_database",
      ),
      region: optional(str),
      country: optional(str),
      source_id: optional(str),
      date: optional(str),
    }),
  ),
  candidates: arr(candidate),
  disclaimer: str,
});

// --- cascades (cascade-engine design §3.6) -----------------------------------------------------

const side = {
  ingredient_key: str,
  label_en: nullable(str),
  items: arr(int, 1),
  matched_codes: strs,
  form_confirmed: bool,
  start: nullable(month),
};

export const finding = obj({
  finding_id: str,
  rule_id: pattern(/^pipc:[0-9]+$/),
  rule_evidence_id: str,
  rule_text: obj({
    system: str,
    kind: str,
    drug_a: str,
    adverse_event: str,
    drug_b: str,
    locator: str,
  }),
  index: obj({ ...side, via_form_extension: bool }),
  marker: obj(side),
  status: lit("probable", "possible"),
  timing: lit("within_window", "date_unknown", "same_month", "after_window"),
  months_between: nullable(int),
  low_priority: bool,
  form_confirmed: bool,
  via_form_extension: bool,
  priority: nullable(
    obj({
      source: lit("bmj_2026_abstract"),
      measure: lit("incidence", "adjusted_sequence_ratio"),
      value: str,
      ci_low: str,
      ci_high: str,
      unit: lit("percent", "ratio"),
      locator: str,
      evidence_id: str,
    }),
  ),
  abrupt_stop: arr(lit("index", "marker")),
  evidence_ids: strs,
  excluded_evidence: arr(obj({ id: str, reason: str })),
  integrity_codes: strs,
  faers_locator: optional(str),
  codes: arr(lit("matches_published_pattern")),
});

export const notCheckedReason = lit(
  "homeopathic_product",
  "ambiguous",
  "no_ingredient_key",
  "possible_unsplit_combination",
  "no_ingredient_atc",
  "no_ingredient_atc_for_route",
);

export const cascadeResult = obj({
  rule_base_version: hex64,
  dataset_version: hex64,
  integrity_version: hex64,
  as_of_month: month,
  window_months: int,
  findings: arr(finding),
  chains: arr(
    obj({
      chain_id: str,
      ingredient_keys: arr(str, 2),
      links: arr(
        obj({ index_key: str, marker_key: str, finding_ids: arr(str, 1) }),
        1,
      ),
      status: lit("probable", "possible"),
    }),
  ),
  same_product: arr(
    obj({ rule_id: str, index_key: str, marker_key: str, items: arr(int) }),
  ),
  item_warnings: arr(
    obj({
      item: int,
      ingredient_key: str,
      code: lit("do_not_stop_suddenly"),
      text: str,
    }),
  ),
  not_checked: arr(obj({ item: int, position: int, reason: notCheckedReason })),
  rules: obj({
    total: int,
    checked: int,
    disabled: arr(
      obj({
        rule_id: str,
        reason: lit("no_source", "all_sources_retracted", "no_citable_source"),
        removed: arr(
          obj({ id: str, reason: str, notice_types: strs, notice_dois: strs }),
        ),
      }),
    ),
    not_matchable: arr(
      obj({
        rule_id: str,
        role: lit("index", "marker", "both"),
        reason: lit("no_atc_code", "not_a_drug_class", "ambiguous_text"),
      }),
    ),
  }),
  statement: nullable(
    obj({ code: lit("no_pattern_found", "rule_base_unavailable"), text: str }),
  ),
  notices: arr(lit("chains_truncated")),
  disclaimer: str,
});

// --- evidence integrity (evidence-integrity design §3.4) ---------------------------------------

const integrityStatus = lit(
  "ok",
  "corrected",
  "expression_of_concern",
  "retracted",
  "unknown",
);

const integrityView = obj({
  status: integrityStatus,
  check_status: integrityStatus,
  reason: nullable(str),
  checked_at: nullable(date),
  check_age_days: nullable(int),
  check_stale: bool,
  notices: arr(
    obj({
      type: str,
      source: nullable(str),
      date: nullable(date),
      notice_doi: nullable(str),
      notice_url: nullable(str),
    }),
  ),
});

const freshness = obj({
  state: lit("current", "stale", "not_applicable"),
  age_days: int,
  limit_days: nullable(int),
});

const exclusionReason = lit("retracted", "not_registered", "no_citable_basis");

export const evidenceItem = obj({
  id: str,
  registered: bool,
  kind: nullable(str),
  title: nullable(str),
  doi: nullable(str),
  locator: nullable(str),
  source: nullable(
    obj({
      source_id: str,
      name: nullable(str),
      source_url: str,
      license: str,
      region: nullable(str),
      snapshot_date: date,
      snapshot_is_retrieval_time: bool,
    }),
  ),
  freshness: nullable(freshness),
  doi_check: lit("checked", "not_applicable"),
  integrity: nullable(integrityView),
  roots: arr(
    obj({
      id: str,
      title: nullable(str),
      doi: nullable(str),
      citable: bool,
      integrity: nullable(integrityView),
      freshness: nullable(freshness),
    }),
  ),
  citable: bool,
  exclusion_reason: nullable(exclusionReason),
  codes: arr(
    lit(
      "corrected_notice",
      "expression_of_concern_notice",
      "integrity_unknown",
      "source_may_be_outdated",
      "integrity_check_may_be_out_of_date",
      "excluded_retracted",
      "not_registered",
    ),
  ),
});

export const evidenceResolution = obj({
  integrity_version: str,
  as_of: date,
  items: arr(evidenceItem),
  citable_ids: strs,
  excluded: arr(obj({ id: str, reason: exclusionReason })),
  line: obj({
    sources_total: int,
    checked_by_doi: int,
    without_doi_check: int,
    by_status: obj({
      ok: int,
      corrected: int,
      expression_of_concern: int,
      unknown: int,
    }),
    oldest_check: nullable(date),
    newest_check: nullable(date),
    stale_sources: arr(
      obj({
        source_id: str,
        snapshot_date: date,
        age_days: int,
        limit_days: int,
      }),
    ),
    integrity_check_stale: bool,
    excluded: arr(obj({ id: str, reason: exclusionReason })),
    no_retracted_used: bool,
  }),
  disclaimer: str,
});

export const evidenceChange = obj({
  evidence_id: str,
  title: nullable(str),
  doi: nullable(str),
  from_status: integrityStatus,
  to_status: integrityStatus,
  observed_on: date,
  run_id: nullable(str),
});

/** `POST /evidence/changes` (evidence-integrity Req 7.2; zombie-alert design §3.2). */
export const changesResult = obj({
  integrity_version: str,
  as_of: date,
  since: nullable(date),
  observed_dates: arr(date),
  status_counts: obj({
    ok: int,
    corrected: int,
    expression_of_concern: int,
    retracted: int,
    unknown: int,
  }),
  changes: arr(evidenceChange),
  disclaimer: str,
});

// --- Collective Memory (collective-memory design §5) -------------------------------------------

const region6 = lit("ALL", "TR", "EU", "US", "OTHER", "UNKNOWN");
const scope = lit("suspect", "any");
export const assessment = lit(
  "no_reports",
  "insufficient_data",
  "not_disproportionate",
  "weak",
  "disproportionate",
);
const citation = obj({ evidence_id: lit("dataset:faers"), locator: str });
const cells = obj({ a: int, b: int, c: int, d: int, n: int });
const estimates = obj({
  prr: num,
  ror: num,
  ror_ci: obj({ low: num, high: num, level: num, method: str }),
  chi2: num,
  chi2_form: str,
});

export const stats = obj({
  region: region6,
  scope,
  cells,
  haldane_applied: bool,
  estimates: nullable(estimates),
  evans_met: bool,
  ror_signal: bool,
  assessment,
  sensitivity: obj({
    cells,
    haldane_applied: bool,
    estimates: nullable(estimates),
    assessment,
    differs: bool,
  }),
  denominator_sensitive: bool,
  codes: strs,
});

const eventOut = obj({
  pt: nullable(str),
  key: nullable(str),
  pts: strs,
  reported_in_window: bool,
  safety_line: nullable(str),
});

const faersCommon = {
  layer: lit("faers"),
  snapshot: obj({
    build_id: str,
    snapshot_date: date,
    window: strs,
    faers_run_id: str,
    resolution_dataset_version: str,
    served_resolution_dataset_version: nullable(str),
    counts_match_served: nullable(bool),
    stale: bool,
    age_days: int,
  }),
  notices: strs,
  disclaimer: str,
  attribution: str,
  meddra_notice: nullable(str),
};

export const pairOut = obj({
  ...faersCommon,
  status: lit("ok", "not_available"),
  ingredient: str,
  event: eventOut,
  stats: nullable(stats),
  citation: nullable(citation),
});

const eventStats = obj({
  pt: str,
  reports: int,
  stats,
  safety_line: nullable(str),
  members_alone: arr(obj({ key: str, reports: int })),
  citation,
});

export const combinationOut = obj({
  ...faersCommon,
  region: region6,
  scope,
  level: lit("combination", "pairwise", "single"),
  exposure: lit("all_of_set"),
  comparison: lit("all_other_mapped_reports"),
  skipped: arr(
    obj({ level: lit("combination", "pairwise", "single"), reason: str }),
  ),
  ingredients: arr(
    obj({
      key: str,
      reports: int,
      citation,
      assessment: lit("no_reports", "ok"),
    }),
  ),
  combination: obj({ reports: int, n: int }),
  citation,
  events: arr(eventStats),
  pairs: arr(
    obj({
      keys: strs,
      reports: int,
      citation,
      events_omitted: bool,
      events: arr(eventStats),
    }),
  ),
  singles: arr(
    obj({ key: str, reports: int, citation, events: arr(eventStats) }),
  ),
});

export const regionsOut = obj({
  ...faersCommon,
  scope,
  event: nullable(eventOut),
  rows: arr(
    obj({
      region: region6,
      n_primary: int,
      n_all: int,
      reports: int,
      stats: nullable(stats),
      citation: nullable(citation),
    }),
  ),
  unknown: obj({ reports: int, share: num }),
  basis: arr(obj({ region: region6, occurrence: int, reporter_fallback: int })),
  adrreports_url: str,
});

export const sharedOut = obj({
  layer: lit("contributions", "outcomes"),
  status: lit("ok", "layer_unavailable", "not_available"),
  cells: arr(
    obj({
      region: lit("TR", "EU", "US"),
      status: lit("released", "hidden"),
      value: optional(int),
    }),
  ),
  total_of_released: nullable(int),
  disclosure: obj({
    k: int,
    epsilon: str,
    wording: lit("hidden_under_20_noise_added"),
  }),
  disclaimer: str,
  notices: strs,
});

export const snapshotOut = obj({
  build_id: str,
  snapshot_date: date,
  window: strs,
  faers_run_id: str,
  resolution_dataset_version: str,
  stale: bool,
  age_days: int,
  totals: arr(obj({ region: region6, reports_mapped: int, reports_all: int })),
  unknown_share: num,
  layers: record(str),
  notices: strs,
  meddra_notice: str,
  attribution: str,
});

// --- notes and outcomes (doctor-loop design §4, §7, §9) ----------------------------------------

const text = obj({ template: str, text: str });

export const sentence = obj({
  type: lit("sentence"),
  id: str,
  template: str,
  kind: lit("claim", "fixed"),
  text: str,
  evidence_ids: strs,
  numbers: strs,
});

export const medicineRow = obj({
  type: lit("medicine"),
  item: int,
  product_name_slot: lit(true),
  product_label: text,
  ingredients: arr(
    obj({
      key: str,
      name: nullable(text),
      name_basis: lit(
        "glossary",
        "english_fallback",
        "not_reviewed",
        "code_only",
      ),
      tag: nullable(text),
      atc: strs,
      combination_code: optional(text),
    }),
  ),
  not_checked: arr(obj({ position: int, reason: str, text })),
  started: text,
  abrupt_stop: nullable(sentence),
});

export const statRow = obj({
  type: lit("stat"),
  id: str,
  finding_ids: strs,
  region: str,
  ingredient_key: str,
  event_key: str,
  reports: nullable(int),
  assessment: str,
  estimates: nullable(obj({ ror: num, low: num, high: num })),
  pts: nullable(text),
  citation: obj({ evidence_id: lit("dataset:faers"), locator: str }),
  sentences: arr(sentence),
});

export const SECTION_ORDER = [
  "header",
  "safety",
  "medicines",
  "findings",
  "findings_form_unconfirmed",
  "chains",
  "statistics",
  "scope",
  "integrity",
  "outcome_loop",
  "about",
] as const;

export const noteDocument = obj({
  language: lit("en", "tr", "de", "fr", "es"),
  sections: arr(
    obj({
      id: lit(...SECTION_ORDER),
      heading: nullable(text),
      blocks: arr(
        tagged("type", { sentence, medicine: medicineRow, stat: statRow }),
      ),
    }),
  ),
});

export const noteOut = obj({
  note_format: lit("janus-note-1"),
  versions: obj({
    rule_base_version: str,
    dataset_version: str,
    integrity_version: str,
    counts_build_id: nullable(str),
    glossary_version: str,
  }),
  as_of_month: month,
  removals: arr(
    obj({
      sentence_id: str,
      reason: lit(
        "no_evidence",
        "evidence_not_citable",
        "forbidden_phrase",
        "reassurance_word",
        "foreign_number",
      ),
    }),
  ),
  documents: arr(noteDocument, 1, 2),
});

export const tokenOut = obj({
  token: pattern(/^[A-Za-z0-9_-]{40,4096}$/),
  qr_url: nullable(str),
  expires_on: date,
  findings_covered: int,
  findings_total: int,
  note: noteOut,
});

const option = obj({ code: str, text: str });
const namedIngredient = obj({
  key: str,
  name: str,
  name_basis: str,
  tag: nullable(str),
  atc: strs,
});

export const outcomeFormOut = obj({
  language: lit("en", "tr", "de", "fr", "es"),
  expires_on: date,
  findings: arr(
    obj({
      ref: int,
      rule_id: str,
      cascade: obj({ drug_a: str, adverse_event: str, drug_b: str }),
      index: namedIngredient,
      marker: namedIngredient,
      form_confirmed: bool,
      action_on: arr(option),
    }),
  ),
  options: obj({ assessment: arr(option), action: arr(option) }),
  texts: obj({
    heading: str,
    intro: str,
    stored_fields: str,
    limits: str,
    question_assessment: str,
    question_action: str,
    disclaimer: str,
  }),
});

export const outcomeStoredOut = obj({ stored: int });
export const withdrawnOut = obj({ status: lit("withdrawn") });

// --- donations and privacy (privacy design §3) -------------------------------------------------

export const contributionCreated = obj({
  deletion_token: pattern(/^jdt_[A-Za-z0-9_-]{43}$/),
  stored: obj({
    report_week: date,
    age_band: int,
    sex: nullable(lit("female", "male")),
    region: lit("TR", "EU", "US"),
    ingredients: strs,
    event: str,
    direction: lit("adverse", "benefit"),
    consent_version: str,
  }),
});

export const deletionDone = obj({ deleted: lit(true) });

export const storageInfo = obj({
  donation_storage_region: nullable(str),
  in_eu: bool,
  donations_enabled: bool,
});

/** Error bodies name a code and field paths only; read leniently (a missing code is "unknown"). */
export function errorBody(v: unknown): {
  error: string | null;
  fields: string[];
} {
  if (typeof v !== "object" || v === null) return { error: null, fields: [] };
  const o = v as Record<string, unknown>;
  const error = typeof o.error === "string" ? o.error : null;
  const fields = Array.isArray(o.fields)
    ? o.fields.filter((f): f is string => typeof f === "string")
    : [];
  return { error, fields };
}

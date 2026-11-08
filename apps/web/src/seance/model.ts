/**
 * Séance answers (séance design §7): decoders written from the Pydantic models in
 * `apps/api/janus/seance/schemas.py`, types inferred from them so the two cannot drift apart.
 * There is no score, strength or "proven" field in the contract, and none is decoded.
 */
import {
  arr,
  bool,
  int,
  lit,
  nullable,
  num,
  obj,
  str,
  type Infer,
} from "@/api/decode";

const strs = arr(str);

export const CONDITIONS = ["wound", "burn", "ulcer", "infection"] as const;
export const WITNESSES = ["past", "present", "science"] as const;
export type Condition = (typeof CONDITIONS)[number];
export type WitnessName = (typeof WITNESSES)[number];

export const MISSING = [
  "no_canon_passage",
  "passages_rejected_by_review",
  "no_faers_mapping",
  "exposure_differs",
  "counts_unavailable",
  "no_protective_association",
  "too_few_reports",
  "no_study_listed",
  "no_citable_study",
  "studies_do_not_support",
  "integrity_unavailable",
] as const;
export const PRESENT_CODES = [
  "spontaneous_reports",
  "reports_not_people",
  "not_deduplicated_across_cases",
  "reporting_bias_notoriety_indication",
  "screening_pattern_not_effect",
] as const;
export const STUDY_TYPES = [
  "systematic_review",
  "rct",
  "clinical_other",
  "animal",
  "in_vitro",
  "narrative_review",
] as const;
export const INTEGRITY = [
  "ok",
  "corrected",
  "expression_of_concern",
  "unknown",
] as const;
export const HEADLINE_REASONS = [
  "no_eligible_passage",
  "hazardous_substance",
] as const;

const condition = lit(...CONDITIONS);
const confidence = lit("none", "low", "moderate");
const missing = nullable(lit(...MISSING));
const interval = obj({ low: num, high: num, level: num });

export const substance = obj({
  id: str,
  name_en: str,
  transliteration: str,
  heading_ar: str,
  kind: str,
  identification: str,
  identification_status: lit("matches_gold", "uncertain", "not_in_gold"),
  identification_label: lit("identified", "uncertain"),
  gold: nullable(obj({ gold_id: str, scientific_name: str, citation: str })),
  hamdard_ref: nullable(str),
  hazard: nullable(lit("toxic", "caustic")),
  note: str,
});

const source = obj({ id: str, citation: str, license: str });

export const catalogueOut = obj({
  schema_version: lit("seance-1"),
  substances: arr(substance),
  pairs: arr(
    obj({
      substance: str,
      condition,
      past_passages: int,
      science_studies: int,
      present_link: lit("same", "component", "different", "none"),
      present_ingredient_key: nullable(str),
    }),
  ),
  sources: arr(source),
  disclaimer: str,
});

const pastItem = obj({
  claim_id: str,
  locator: obj({
    entry_id: str,
    span_id: str,
    book: int,
    page: nullable(str),
    line_start: int,
    line_end: int,
  }),
  arabic_span: str,
  translation: str,
  translation_kind: lit("machine_translation"),
  use_en: str,
  ai_review: lit("passed_both"),
  expert_review: lit("pending", "reviewed"),
  headline_eligible: bool,
});

const presentItem = obj({
  ingredient_key: str,
  exposure_match: lit("same", "component"),
  reports_with_both: int,
  reports_with_ingredient: int,
  ror: num,
  ror_ci: interval,
  region: lit("ALL"),
  scope: lit("suspect"),
  snapshot_date: str,
});

const observed = obj({
  ingredient_key: str,
  exposure_match: lit("same", "component", "different"),
  reports_with_both: int,
  reports_with_ingredient: int,
  ror: nullable(num),
  ror_ci: nullable(interval),
  snapshot_date: str,
});

const scienceItem = obj({
  evidence_id: str,
  doi: str,
  title: str,
  study_type: lit(...STUDY_TYPES),
  finding_en: str,
  integrity_status: lit(...INTEGRITY),
});

const witness = { supports: bool, confidence, missing_reason: missing };

export const seanceOut = obj({
  schema_version: lit("seance-1"),
  substance,
  condition,
  witnesses: obj({
    past: obj({ ...witness, items: arr(pastItem) }),
    present: obj({
      ...witness,
      items: arr(presentItem),
      observed: nullable(observed),
      pts: strs,
      // A caveat the screen cannot word is a contract error, never a raw key on screen.
      codes: arr(lit(...PRESENT_CODES)),
    }),
    science: obj({ ...witness, items: arr(scienceItem), excluded: strs }),
  }),
  supporting_witnesses: lit(0, 1, 2, 3),
  missing_witnesses: arr(lit(...WITNESSES)),
  framing: lit("hypothesis_not_treatment"),
  headline: obj({ eligible: bool, reasons: strs }),
  sources: arr(source),
  disclaimer: str,
});

export type Substance = Infer<typeof substance>;
export type CatalogueOut = Infer<typeof catalogueOut>;
export type PairSummary = CatalogueOut["pairs"][number];
export type SeanceOut = Infer<typeof seanceOut>;
export type PastItem = SeanceOut["witnesses"]["past"]["items"][number];
export type PresentWitness = SeanceOut["witnesses"]["present"];
export type ScienceWitness = SeanceOut["witnesses"]["science"];
export type SeanceIn = { substance: string; condition: Condition };

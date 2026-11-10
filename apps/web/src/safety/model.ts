/**
 * `POST /safety/check` (safety-check design §7): strict response decoder, written from the
 * Pydantic models in apps/api/janus/safety/schemas.py. The request is the evaluation body.
 */
import * as D from "@/api/decode";
import type { Infer } from "@/api/decode";

const KEY = D.pattern(/^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$/);
const items = D.arr(D.int, 1, 50);

export const member = D.obj({
  ingredient_key: KEY,
  label_en: D.nullable(D.str),
  items,
  codes: D.arr(D.pattern(/^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$/)),
  form_confirmed: D.bool,
});

export const duplicationFinding = D.obj({
  finding_id: D.str,
  kind: D.lit("same_ingredient", "same_group"),
  atc_group: D.nullable(D.pattern(/^[A-Z][0-9]{2}[A-Z]{2}$/)),
  members: D.arr(member, 1, 50),
  items: D.arr(D.int, 2, 50),
  form_confirmed: D.bool,
});

export const duplication = D.obj({
  status: D.lit("checked"),
  atc_level: D.lit(4),
  findings: D.arr(duplicationFinding),
  sources: D.arr(D.sourceRef),
  statement: D.nullable(D.obj({ code: D.lit("no_duplication_found") })),
});

const DATE = D.pattern(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/);

const ingredientRef = D.obj({
  ingredient_key: KEY,
  label_en: D.nullable(D.str),
  items,
});

const labelOut = D.obj({
  substance_name: D.str,
  set_id: D.str,
  version: D.nullable(D.str),
  effective_date: D.nullable(DATE),
  product_type: D.nullable(D.str),
  url: D.pattern(
    /^https:\/\/dailymed\.nlm\.nih\.gov\/dailymed\/drugInfo\.cfm\?setid=[A-Za-z0-9._~%-]+$/,
  ),
});

export const interactionFinding = D.obj({
  finding_id: D.str,
  label_of: ingredientRef,
  names: ingredientRef,
  matched_name: D.str,
  label: labelOut,
  passages: D.arr(
    D.obj({ text: D.str, cut_start: D.bool, cut_end: D.bool }),
    1,
    10,
  ),
  total_passages: D.int,
  codes: D.arr(D.lit("label_text_names_ingredient")),
});

export const interactions = D.obj({
  status: D.lit("checked", "unavailable"),
  rules_version: D.str,
  source: D.nullable(
    D.obj({
      source_id: D.lit("openfda_label_interactions"),
      run_id: D.str,
      snapshot_date: DATE,
      license: D.str,
      url: D.str,
      terms_url: D.str,
      labels: D.int,
    }),
  ),
  findings: D.arr(interactionFinding),
  total_findings: D.int,
  truncated: D.bool,
  labels_read: D.arr(
    D.obj({
      ingredient_key: KEY,
      label_en: D.nullable(D.str),
      items,
      label: labelOut,
    }),
  ),
  labels_not_found: D.arr(ingredientRef),
  statement: D.nullable(D.obj({ code: D.lit("no_label_passage_found") })),
  notices: D.arr(D.str),
});

export const safetyCheckOut = D.obj({
  dataset_version: D.str,
  items: D.int,
  ingredients_checked: D.int,
  not_checked: D.arr(D.obj({ item: D.int, position: D.int })),
  duplication,
  interactions,
});

export type Member = Infer<typeof member>;
export type DuplicationFinding = Infer<typeof duplicationFinding>;
export type Duplication = Infer<typeof duplication>;
export type InteractionFinding = Infer<typeof interactionFinding>;
export type Interactions = Infer<typeof interactions>;
export type SafetyCheckOut = Infer<typeof safetyCheckOut>;

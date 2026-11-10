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

export const safetyCheckOut = D.obj({
  dataset_version: D.str,
  items: D.int,
  ingredients_checked: D.int,
  not_checked: D.arr(D.obj({ item: D.int, position: D.int })),
  duplication,
});

export type Member = Infer<typeof member>;
export type DuplicationFinding = Infer<typeof duplicationFinding>;
export type Duplication = Infer<typeof duplication>;
export type SafetyCheckOut = Infer<typeof safetyCheckOut>;

/**
 * `POST /medicine-info` (plain-medicine-info design §6): request type and strict response
 * decoder, written from the Pydantic models in apps/api/janus/plaininfo/router.py.
 */
import type { Locale } from "@/api/contracts";
import * as D from "@/api/decode";
import type { Infer } from "@/api/decode";

const date = D.pattern(/^\d{4}-\d{2}-\d{2}$/);
const atc = D.pattern(/^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$/);

export interface IngredientIn {
  atc_codes: string[];
}
export type ProductIn =
  { country: "US"; ndc: string } | { country: "FR" | "ES"; name: string };
export interface MedicineInfoIn {
  language: Locale;
  ingredients: IngredientIn[];
  product?: ProductIn;
}

export const STATUSES = ["single", "mixed", "none"] as const;
export const OFFICIAL_STATUSES = [
  "text",
  "page",
  "not_asked",
  "not_found",
  "several_labels",
  "source_unavailable",
] as const;

export const group = D.obj({
  id: D.pattern(/^[a-z][a-z0-9_]{1,39}$/),
  name: D.pattern(/\S/),
  text: D.pattern(/\S/),
  codes: D.arr(atc, 1),
  review_status: D.lit("not_reviewed", "expert_reviewed"),
});

export const ingredient = D.obj({
  status: D.lit(...STATUSES),
  groups: D.arr(group),
  other_uses: D.bool,
  abrupt_stop: D.bool,
});

const source = D.obj({
  source_id: D.lit("openfda_label_indications", "bdpm", "cima"),
  run_id: D.str,
  snapshot_date: date,
});

export const labelText = D.obj({
  kind: D.lit("label_text"),
  country: D.lit("US"),
  language: D.lit("en"),
  paragraphs: D.arr(D.str, 1),
  truncated: D.bool,
  version: D.nullable(D.str),
  effective_date: D.nullable(date),
  url: D.pattern(
    /^https:\/\/dailymed\.nlm\.nih\.gov\/dailymed\/drugInfo\.cfm\?setid=[0-9a-f-]{36}$/,
  ),
  source,
});

export const productPage = D.obj({
  kind: D.lit("product_page"),
  country: D.lit("FR", "ES"),
  language: D.lit("fr", "es"),
  url: D.pattern(
    /^https:\/\/(base-donnees-publique\.medicaments\.gouv\.fr\/medicament\/[0-9]{8}\/extrait|cima\.aemps\.es\/cima\/publico\/detalle\.html\?nregistro=[0-9]{4,10})$/,
  ),
  source,
});

export const medicineInfoOut = D.obj({
  language: D.lit("en", "tr", "de", "fr", "es"),
  groups_version: D.pattern(/^[0-9a-f]{64}$/),
  ingredients: D.arr(ingredient, 0, 12),
  official: D.nullable(
    D.tagged("kind", { label_text: labelText, product_page: productPage }),
  ),
  official_status: D.lit(...OFFICIAL_STATUSES),
  // Fixed codes; a code this client does not know is ignored, not refused.
  notices: D.arr(D.str),
});

export type GroupOut = Infer<typeof group>;
export type IngredientOut = Infer<typeof ingredient>;
export type LabelText = Infer<typeof labelText>;
export type ProductPage = Infer<typeof productPage>;
export type MedicineInfoOut = Infer<typeof medicineInfoOut>;

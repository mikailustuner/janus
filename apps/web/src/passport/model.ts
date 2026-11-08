/**
 * The Passport's list item and the `POST /passport/presence` contract (medication-passport
 * design §3, §6.1). The closed sets mirror `apps/api/janus/passport/schemas.py`; a test compares
 * them with `fixtures/schema-literals.json`, which a Python test exports from the server models.
 * The list lives in the browser only: box names, codes, counts and months never reach a request
 * body (`request.ts`, P18).
 */
import type { Candidate } from "@/api/contracts";
import * as D from "@/api/decode";
import type { Item } from "@/store/list";

export const STATUSES = [
  "present",
  "not_present",
  "not_in_source",
  "source_unavailable",
] as const;
export const RESULTS = ["matched", "differs", "could_not_compare"] as const;
export const CMP_REASONS = [
  "not_known_for_item",
  "not_known_in_source",
  "not_all_comparable",
] as const;
export const NOTICES = [
  "presence_is_lower_bound",
  "unknown_ingredient_keys",
] as const;
export const SOURCE_IDS = [
  "titck",
  "eu_fr_bdpm",
  "eu_es_cima",
  "openfda_ndc",
] as const;
export const FORM_GROUPS = [
  "oral_solid",
  "oral_solid_delayed_release",
  "oral_solid_prolonged_release",
  "oral_liquid",
  "injection",
  "inhaled",
  "nasal",
  "ophthalmic",
  "otic",
  "cutaneous",
  "transdermal",
  "rectal",
  "vaginal",
  "other",
] as const;
export const COUNTABLE_GROUPS = [
  "oral_solid",
  "oral_solid_delayed_release",
  "oral_solid_prolonged_release",
] as const;
export const SOURCE_REGIONS = ["TR", "EU", "US"] as const;
export const SOURCE_COUNTRIES = ["FR", "ES", "DE"] as const;
export const UNAVAILABLE_REASONS = [
  "not_loaded",
  "no_open_product_database",
] as const;
export const ATTRIBUTIONS = ["titck", "bdpm", "cima", "openfda"] as const;
export const UNITS = ["ug", "IU"] as const;
export const BASES = ["unit", "mL", "g"] as const;
export const KEY = /^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$/;
export const AMOUNT = /^(0|[1-9][0-9]{0,8})(\.[0-9]{0,5}[1-9])?$/;
export const MAX_ITEMS = 50;
export const MAX_INGREDIENTS = 10;
export const MAX_KEYS = 50;

export type Key = string;
export type Status = (typeof STATUSES)[number];
export type CmpResult = (typeof RESULTS)[number];
export type CmpReason = (typeof CMP_REASONS)[number];
export type SourceId = (typeof SOURCE_IDS)[number];
export type FormGroup = (typeof FORM_GROUPS)[number];

export interface StrengthCode {
  amount: string;
  unit: (typeof UNITS)[number];
  basis: (typeof BASES)[number];
}

/** Where a box comes from; `country` is null when only the region is known. */
export interface Origin {
  region: "TR" | "EU" | "US" | "OTHER";
  country: "TR" | "FR" | "ES" | "DE" | "US" | null;
}
export type ValueOrigin = "source" | "entered";

export interface PassportIngredient {
  key: Key | null;
  /** The name to show: the vocabulary's ingredient name, else the name as published. */
  label: string;
  status: "mapped" | "ambiguous" | "unmapped";
  strength: StrengthCode | null;
  strengthOrigin: ValueOrigin | null;
}

export interface PassportItem {
  id: string;
  demo: boolean;
  origin: Origin;
  source:
    { source_id: string; snapshot_date: string } | { entered_by_name: true };
  code: { kind: string; value: string } | null;
  boxName: string;
  ingredients: PassportIngredient[];
  doseForm: { group: FormGroup; origin: ValueOrigin } | null;
  homeopathic: boolean;
  boxes: number;
  started: string | null;
}

// --- request (`PresenceIn`, strict on the server) -----------------------------------------------
export interface IngredientIn {
  key: Key;
  strength?: StrengthCode;
}
export interface ItemIn {
  ingredients: IngredientIn[];
  dose_form?: FormGroup;
}
export interface PresenceIn {
  items: ItemIn[];
}

// --- response (`PresenceOut`) -------------------------------------------------------------------
const int = D.int;
const cmp = D.obj({
  result: D.lit(...RESULTS),
  reason: D.nullable(D.lit(...CMP_REASONS)),
  comparable: int,
  equal: int,
});
const keys = D.arr(D.pattern(KEY));

export const sourceOut = D.obj({
  source: int,
  source_id: D.nullable(D.lit(...SOURCE_IDS)),
  region: D.lit(...SOURCE_REGIONS),
  country: D.nullable(D.lit(...SOURCE_COUNTRIES)),
  status: D.lit("loaded", "source_unavailable"),
  reason: D.nullable(D.lit(...UNAVAILABLE_REASONS)),
  snapshot_date: D.nullable(D.pattern(/^\d{4}-\d{2}-\d{2}$/)),
  stale: D.bool,
  attribution: D.nullable(D.lit(...ATTRIBUTIONS)),
  as_published: D.bool,
  can_compare: D.obj({ strength: D.bool, dose_form: D.bool }),
});

export const answer = D.obj({
  source: int,
  status: D.lit(...STATUSES),
  products: int,
  with_other_ingredients: int,
  keys_found: keys,
  homeopathic_left_out: int,
  comparison: D.nullable(
    D.obj({ strength: cmp, dose_form: cmp, strength_and_dose_form: cmp }),
  ),
});

export const presenceOut = D.obj({
  dataset_version: D.pattern(/^[0-9a-f]{64}$/),
  form_table_version: D.pattern(/^[0-9a-f]{64}$/),
  sources: D.arr(sourceOut, 5, 5),
  items: D.arr(
    D.obj({
      item: int,
      keys,
      unknown_keys: keys,
      answers: D.arr(answer, 5, 5),
    }),
  ),
  notices: D.arr(D.lit(...NOTICES)),
  disclaimer: D.str,
});

export type SourceOut = D.Infer<typeof sourceOut>;
export type Answer = D.Infer<typeof answer>;
export type Cmp = D.Infer<typeof cmp>;
export type PresenceOut = D.Infer<typeof presenceOut>;
export type ItemOut = PresenceOut["items"][number];

// --- from the experience list store (Req 26.1) ------------------------------------------------

const isFormGroup = (v: string | null | undefined): v is FormGroup =>
  (FORM_GROUPS as readonly (string | null | undefined)[]).includes(v);

function originOf(item: Item): Origin {
  const c: Candidate = item.candidate;
  if (c.kind === "product") {
    if (c.region === "EU") return { region: "EU", country: c.country ?? null };
    return { region: c.region, country: c.region };
  }
  const region =
    item.sourceKey.kind === "search" ? item.sourceKey.region : null;
  if (region === "EU") return { region: "EU", country: null };
  return region
    ? { region, country: region }
    : { region: "OTHER", country: null };
}

/**
 * A list item of the experience store as a Passport item (one box; the store keeps one item per
 * box). Names come from `label` (the caller's vocabulary lookup); nothing is invented here.
 */
export function fromListItem(
  item: Item,
  label: (key: Key | null, published: string) => string,
  demo = false,
): PassportItem {
  const c = item.candidate;
  const base = {
    id: item.id,
    demo,
    origin: originOf(item),
    boxName: item.boxName,
    boxes: 1,
    started: item.started,
  };
  if (c.kind === "ingredient")
    return {
      ...base,
      source: { entered_by_name: true },
      code: null,
      ingredients: [
        {
          key: c.ingredient_key.qid,
          label: label(c.ingredient_key.qid, c.ingredient_key.label_en ?? ""),
          status: "mapped",
          strength: null,
          strengthOrigin: null,
        },
      ],
      doseForm: null,
      homeopathic: false,
    };
  return {
    ...base,
    source: {
      source_id: c.source.source_id,
      snapshot_date: c.source.snapshot_date,
    },
    // The code read from the box (stable across datasets, unlike candidate ids: DP13).
    code:
      item.sourceKey.kind === "scan"
        ? { kind: "scan", value: item.sourceKey.content }
        : item.sourceKey.kind === "ndc"
          ? { kind: "ndc", value: item.sourceKey.ndc }
          : null,
    ingredients: c.ingredients.map((ing) => {
      const chosen =
        ing.status === "ambiguous"
          ? (item.choices.find((ch) => ch.position === ing.position)
              ?.ingredient ?? null)
          : null;
      const key =
        ing.status === "mapped" ? (ing.ingredient_key?.qid ?? null) : chosen;
      const strength = ing.strength_code ?? null;
      return {
        key,
        label: label(key, ing.published_name),
        status: ing.status,
        strength,
        strengthOrigin: strength ? "source" : null,
      };
    }),
    doseForm: isFormGroup(c.dose_form_group)
      ? { group: c.dose_form_group, origin: "source" }
      : null,
    homeopathic: c.homeopathic,
  };
}

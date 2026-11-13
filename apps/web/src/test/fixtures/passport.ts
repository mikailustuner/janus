/**
 * Synthetic Passport answers for the behaviour tests: the presence answer and the product lists
 * for any request, generated from the request itself (so a test list and its answer always
 * agree), in the shapes of the recorded demo files. Typed with the production types and decoded
 * by the production decoders; nothing is read from the recorded files.
 *
 * Presence: five sources (Turkey, France, Spain, Germany without an open database, United
 * States). A combination of two or more ingredients is listed in the first source only (the
 * others say "not present"); strength and form are compared in the sources that can compare
 * them, when the box gives them.
 * Products: a first page of eight listed products out of 51 for a single ingredient (strength
 * "same" only when the box gives every strength, form "same" only when it gives a form);
 * a combination has no listed product.
 */
import * as D from "@/api/decode";
import type { Recorded } from "@/passport/client";
import {
  presenceOut,
  type Answer,
  type Cmp,
  type ItemIn,
  type PresenceIn,
  type PresenceOut,
  type SourceOut,
} from "@/passport/model";
import {
  productsOut,
  type Level,
  type ProductsIn,
  type ProductsOut,
  type RecordedProducts,
  type Target,
} from "@/passport/products";

const DATASET = "b".repeat(64);
const FORM_TABLE = "c".repeat(64);
const DISCLAIMER =
  "Janus provides information, not medical advice. Research prototype — not a medical device.";
export const RECORDED_ON = "2026-01-01";

export const SOURCES: SourceOut[] = [
  {
    source: 0,
    source_id: "titck",
    region: "TR",
    country: null,
    status: "loaded",
    reason: null,
    snapshot_date: "2026-01-01",
    stale: false,
    attribution: "titck",
    as_published: false,
    can_compare: { strength: false, dose_form: false },
  },
  {
    source: 1,
    source_id: "eu_fr_bdpm",
    region: "EU",
    country: "FR",
    status: "loaded",
    reason: null,
    snapshot_date: "2026-01-01",
    stale: false,
    attribution: "bdpm",
    as_published: true,
    can_compare: { strength: true, dose_form: true },
  },
  {
    source: 2,
    source_id: "eu_es_cima",
    region: "EU",
    country: "ES",
    status: "loaded",
    reason: null,
    snapshot_date: "2026-01-01",
    stale: false,
    attribution: "cima",
    as_published: false,
    can_compare: { strength: false, dose_form: false },
  },
  {
    source: 3,
    source_id: null,
    region: "EU",
    country: "DE",
    status: "source_unavailable",
    reason: "no_open_product_database",
    snapshot_date: null,
    stale: false,
    attribution: null,
    as_published: false,
    can_compare: { strength: false, dose_form: false },
  },
  {
    source: 4,
    source_id: "openfda_ndc",
    region: "US",
    country: null,
    status: "loaded",
    reason: null,
    snapshot_date: "2026-01-01",
    stale: false,
    attribution: "openfda",
    as_published: true,
    can_compare: { strength: true, dose_form: true },
  },
];

const cmp = (
  result: Cmp["result"],
  reason: Cmp["reason"],
  comparable = 0,
  equal = 0,
): Cmp => ({ result, reason, comparable, equal });
const cannot = (reason: "not_known_for_item" | "not_known_in_source") =>
  cmp("could_not_compare", reason);

const hasStrength = (i: ItemIn) => i.ingredients.every((g) => !!g.strength);

function answerFor(item: ItemIn, src: SourceOut, index: number): Answer {
  const keys = item.ingredients.map((g) => g.key);
  const combination = keys.length >= 2;
  if (src.status === "source_unavailable")
    return {
      source: src.source,
      status: "source_unavailable",
      products: 0,
      with_other_ingredients: 0,
      keys_found: [],
      homeopathic_left_out: 0,
      comparison: null,
    };
  if (combination && src.source !== 0)
    return {
      source: src.source,
      status: "not_present",
      products: 0,
      with_other_ingredients: 0,
      keys_found: [],
      homeopathic_left_out: 0,
      comparison: null,
    };
  const canCompare = src.can_compare.strength;
  const strength =
    canCompare && hasStrength(item)
      ? cmp("matched", null, 10, 7)
      : cannot(canCompare ? "not_known_for_item" : "not_known_in_source");
  const form =
    canCompare && item.dose_form
      ? cmp("matched", null, 10, 9)
      : cannot(canCompare ? "not_known_for_item" : "not_known_in_source");
  const both =
    strength.result === "matched" && form.result === "matched"
      ? cmp("matched", null, 10, 6)
      : cannot(canCompare ? "not_known_for_item" : "not_known_in_source");
  return {
    source: src.source,
    status: "present",
    products: 10 + index,
    with_other_ingredients: index % 2,
    keys_found: keys,
    homeopathic_left_out: 0,
    comparison: { strength, dose_form: form, strength_and_dose_form: both },
  };
}

/** The presence answer to a request: one entry per item, one answer per source. */
export function presenceFor(request: PresenceIn): PresenceOut {
  const out: PresenceOut = {
    dataset_version: DATASET,
    form_table_version: FORM_TABLE,
    sources: SOURCES,
    items: request.items.map((item, i) => ({
      item: i,
      keys: item.ingredients.map((g) => g.key),
      unknown_keys: [],
      answers: SOURCES.map((s) => answerFor(item, s, i)),
    })),
    notices: ["presence_is_lower_bound"],
    disclaimer: DISCLAIMER,
  };
  const r = D.decode(presenceOut, out);
  if (!r.ok) throw new Error("synthetic fixture presence does not decode");
  return out;
}

/** A recorded-shaped presence file for one request (the demo's file shape). */
export function presenceRecorded(request: PresenceIn): Recorded {
  return {
    recorded: { date: RECORDED_ON, dataset_version: DATASET },
    request,
    response: presenceFor(request),
  };
}

// --- products --------------------------------------------------------------------------------

const TARGET_SOURCE: Record<Target, SourceOut> = {
  eu_fr_bdpm: SOURCES[1]!,
  eu_es_cima: {
    ...SOURCES[2]!,
    can_compare: { strength: true, dose_form: true },
  },
  openfda_ndc: SOURCES[4]!,
  eu_it_aifa: {
    ...SOURCES[2]!,
    source: 5,
    source_id: "eu_it_aifa",
    country: "IT",
    attribution: "aifa",
  },
  ca_dpd: {
    ...SOURCES[4]!,
    source: 6,
    source_id: "ca_dpd",
    region: "CA",
    country: null,
    attribution: "dpd",
  },
};

const TOTAL = 51;

/** The product list answer for a request (a first page of eight; paging answers the same rows). */
export function productsFor(request: ProductsIn): ProductsOut {
  const keys = request.ingredients.map((g) => g.key);
  const combination = keys.length >= 2;
  const total = combination ? 0 : TOTAL;
  const strength: Level = hasStrength(request) ? "same" : "unknown";
  const form: Level = request.dose_form ? "same" : "unknown";
  const shown = Math.min(request.limit, Math.max(0, total - request.offset), 8);
  const products = Array.from({ length: shown }, (_, n) => ({
    name: `SYNTHETIC PRODUCT ${request.offset + n + 1} ${request.target}`,
    ingredients: request.ingredients.map((g) => ({
      key: g.key,
      strength_published: g.strength ? `${g.strength.amount} ug` : null,
    })),
    dose_form_published: "tablet",
    dose_form_group: request.dose_form ?? "oral_solid",
    strength,
    strength_reason:
      strength === "unknown" ? ("not_known_for_item" as const) : null,
    dose_form: form,
    dose_form_reason:
      form === "unknown" ? ("not_known_for_item" as const) : null,
    marketed: "listed_as_marketed" as const,
    listings: 1,
  }));
  const counts = (level: Level) => ({
    same: level === "same" ? total : 0,
    different: 0,
    unknown: level === "unknown" ? total : 0,
  });
  const out: ProductsOut = {
    dataset_version: DATASET,
    form_table_version: FORM_TABLE,
    source: TARGET_SOURCE[request.target],
    keys,
    unknown_keys: [],
    status: combination ? "not_present" : "present",
    total,
    listings: total,
    counts: { strength: counts(strength), dose_form: counts(form) },
    with_other_ingredients: 0,
    keys_found: combination ? [] : keys,
    homeopathic_left_out: 0,
    not_finished_left_out: 0,
    offset: request.offset,
    limit: request.limit,
    products,
    notices: ["listing_is_lower_bound"],
    disclaimer: DISCLAIMER,
  };
  const r = D.decode(productsOut, out);
  if (!r.ok) throw new Error("synthetic fixture products does not decode");
  return out;
}

/** A recorded-shaped products file: the first page (limit 8) of every request given. */
export function productsRecorded(bodies: ProductsIn[]): RecordedProducts {
  return {
    recorded: { date: RECORDED_ON, dataset_version: DATASET },
    answers: bodies.map((b) => {
      const request = { ...b, offset: 0, limit: 8 };
      return { request, response: productsFor(request) };
    }),
  };
}

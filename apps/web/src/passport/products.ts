/**
 * Products with the same active ingredients in one target source (medication-passport design
 * §15, Req 14–17). The `POST /passport/products` contract mirrors `schemas.py` (a test compares
 * the closed sets with `fixtures/schema-literals.json`). The request is the item's query of
 * `request.ts` (keys, strength codes, form group) plus the target and the page: no box name, code
 * or origin (P29). Only sources whose licence allows showing product names are targets; the TİTCK
 * list is not one (DP28).
 *
 * Demo mode never calls the API (DP26, DP33): the Cologne list's first pages were recorded from
 * the real API (`scripts/record-passport-products.mjs`).
 */
import { HttpClient, type Result } from "@/api/client";
import * as D from "@/api/decode";
import type { ApiError } from "@/api/errors";

import {
  FORM_GROUPS,
  KEY,
  STATUSES,
  sourceOut,
  type ItemIn,
  type PassportItem,
} from "./model";
import { itemQuery, notSentReason } from "./request";

export const LISTABLE = [
  "eu_fr_bdpm",
  "eu_es_cima",
  "openfda_ndc",
  "eu_it_aifa",
  "ca_dpd",
] as const;
export type Target = (typeof LISTABLE)[number];
export const LEVELS = ["same", "different", "unknown"] as const;
export type Level = (typeof LEVELS)[number];
export const LEVEL_REASONS = [
  "not_known_for_item",
  "not_known_in_source",
] as const;
export const MARKETED = [
  "listed_as_marketed",
  "listed_as_not_marketed",
  "not_stated",
] as const;
export const LISTING_NOTICES = [
  "listing_is_lower_bound",
  "unknown_ingredient_keys",
] as const;
export const PAGE = 50;
export const MAX_PAGE = 100;
export const MAX_OFFSET = 100_000;

/** Country of a target (the `Passport.place` and `Passport.country` keys) and the language its
 * source publishes names in (the `lang` of a listed name). */
export const TARGET_COUNTRY: Record<Target, "FR" | "ES" | "US" | "IT" | "CA"> =
  {
    eu_fr_bdpm: "FR",
    eu_es_cima: "ES",
    openfda_ndc: "US",
    eu_it_aifa: "IT",
    ca_dpd: "CA",
  };
export const TARGET_LANG: Record<Target, string> = {
  eu_fr_bdpm: "fr",
  eu_es_cima: "es",
  openfda_ndc: "en",
  eu_it_aifa: "it",
  ca_dpd: "en",
};

export interface ProductsIn extends ItemIn {
  target: Target;
  offset: number;
  limit: number;
}

const int = D.int;
const level = D.lit(...LEVELS);
const reason = D.nullable(D.lit(...LEVEL_REASONS));
const levelCounts = D.obj({ same: int, different: int, unknown: int });
const keys = D.arr(D.pattern(KEY));

export const listedProduct = D.obj({
  name: D.str,
  ingredients: D.arr(
    D.obj({ key: D.pattern(KEY), strength_published: D.nullable(D.str) }),
    1,
  ),
  dose_form_published: D.nullable(D.str),
  dose_form_group: D.nullable(D.lit(...FORM_GROUPS)),
  strength: level,
  strength_reason: reason,
  dose_form: level,
  dose_form_reason: reason,
  marketed: D.lit(...MARKETED),
  listings: int,
});

export const productsOut = D.obj({
  dataset_version: D.pattern(/^[0-9a-f]{64}$/),
  form_table_version: D.pattern(/^[0-9a-f]{64}$/),
  source: sourceOut,
  keys,
  unknown_keys: keys,
  status: D.lit(...STATUSES),
  total: int,
  listings: int,
  counts: D.obj({ strength: levelCounts, dose_form: levelCounts }),
  with_other_ingredients: int,
  keys_found: keys,
  homeopathic_left_out: int,
  not_finished_left_out: int,
  offset: int,
  limit: int,
  products: D.arr(listedProduct, 0, MAX_PAGE),
  notices: D.arr(D.lit(...LISTING_NOTICES)),
  disclaimer: D.str,
});
export type ListedProduct = D.Infer<typeof listedProduct>;
export type ProductsOut = D.Infer<typeof productsOut>;

/** The request for one item, or null when the item cannot be checked (Req 14.9). */
export function buildProductsRequest(
  item: PassportItem,
  target: Target,
  offset = 0,
  limit = PAGE,
): ProductsIn | null {
  if (notSentReason(item) || !LISTABLE.includes(target)) return null;
  return { ...itemQuery(item), target, offset, limit };
}

export type ProductsCall = (body: ProductsIn) => Promise<Result<ProductsOut>>;

const http = new HttpClient();
export const liveProducts: ProductsCall = (body) =>
  http.call("passport/products", "POST", body, productsOut);

export interface RecordedProducts {
  recorded: { date: string; dataset_version: string };
  answers: { request: ProductsIn; response: unknown }[];
}

/** The recorded first page for `body` (same query and target), or null when not recorded. */
export function fromRecordedProducts(
  rec: RecordedProducts,
  body: ProductsIn,
): ProductsOut | null {
  const want = JSON.stringify({ ...body, offset: 0, limit: 0 });
  const hit = rec.answers.find(
    (a) => JSON.stringify({ ...a.request, offset: 0, limit: 0 }) === want,
  );
  return hit ? productsOut(hit.response, "$") : null;
}

export type ProductsState =
  | { status: "loading" }
  | { status: "error"; error: ApiError | null }
  | { status: "not_in_demo" }
  | {
      status: "ok";
      /** The first page's answer (counts, source, notices). */
      out: ProductsOut;
      /** Every row loaded so far, in the server's order. */
      products: ListedProduct[];
      recordedOn: string | null;
      more: "idle" | "loading" | "error";
    };

/** The first page: live, or the recorded answer in demo mode (`call` is null). */
export async function loadProducts(
  body: ProductsIn,
  call: ProductsCall | null,
  recorded: RecordedProducts | null = null,
): Promise<ProductsState> {
  if (!call) {
    const out = recorded ? fromRecordedProducts(recorded, body) : null;
    return out
      ? {
          status: "ok",
          out,
          products: out.products,
          recordedOn: recorded!.recorded.date,
          more: "idle",
        }
      : { status: "not_in_demo" };
  }
  const res = await call(body);
  if (!res.ok) return { status: "error", error: res.error };
  return {
    status: "ok",
    out: res.data,
    products: res.data.products,
    recordedOn: null,
    more: "idle",
  };
}

/** The next page appended; a failure keeps the rows already shown (`more: "error"`). */
export async function loadMore(
  state: Extract<ProductsState, { status: "ok" }>,
  body: ProductsIn,
  call: ProductsCall,
): Promise<Extract<ProductsState, { status: "ok" }>> {
  const res = await call({ ...body, offset: state.products.length });
  // A changed dataset between pages would mix two lists: treated as a failure.
  if (!res.ok || res.data.dataset_version !== state.out.dataset_version)
    return { ...state, more: "error" };
  return {
    ...state,
    products: [...state.products, ...res.data.products],
    more: "idle",
  };
}

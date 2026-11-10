/**
 * What the page asks about one medicine of the list (plain-medicine-info design §8). Pure.
 *
 * Ingredients: those drug resolution could check, each with its ingredient-level ATC codes.
 * Product: a US product by its one product code (as the recall check derives it), a French
 * product by `product_name` and a Spanish one by `brand_name` (the names the API's tables are
 * keyed by). Nothing else of the item is ever part of the request: not the box name the person
 * typed, the lot, the start month or the item id. A homeopathic product and a demo product get
 * no official part.
 */
import type { Candidate, Locale } from "@/api/contracts";
import { candidateIngredients, type ShownIngredient } from "@/components/names";
import type { Item } from "@/store/list";
import type { Loaded } from "@/vocabulary";

import type { MedicineInfoIn, ProductIn } from "./model";

export const MAX_INGREDIENTS = 12;
export const MAX_CODES = 20;
const ATC = /^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$/;

export type NoProductReason =
  "demo" | "homeopathic" | "by_name" | "country" | "no_code";

export interface InfoQuery {
  /** The ingredients as shown, in order; `asked[i]` is the index in `body.ingredients` or null. */
  shown: ShownIngredient[];
  asked: (number | null)[];
  /** Null when there is nothing to ask: every ingredient is unchecked and there is no product. */
  body: MedicineInfoIn | null;
  noProduct: NoProductReason | null;
}

/** The ingredient-level codes of one shown ingredient, sorted, without repeats. */
export function codesOf(g: ShownIngredient): string[] {
  return [...new Set(g.codes.filter((c) => ATC.test(c)))]
    .sort()
    .slice(0, MAX_CODES);
}

export function productOf(
  c: Candidate,
  demo: boolean,
): { product: ProductIn | null; reason: NoProductReason | null } {
  const no = (reason: NoProductReason) => ({ product: null, reason });
  if (c.kind !== "product") return no("by_name");
  if (demo) return no("demo");
  if (c.homeopathic) return no("homeopathic");
  if (c.region === "US") {
    const products = new Set(
      c.packages
        .map((p) => p.ndc11)
        .filter((k) => /^\d{11}$/.test(k))
        .map((k) => k.slice(0, 9)),
    );
    if (products.size !== 1) return no("no_code");
    const p = [...products][0]!;
    return {
      product: { country: "US", ndc: `${p.slice(0, 5)}-${p.slice(5)}` },
      reason: null,
    };
  }
  if (c.country === "FR" || c.country === "ES") {
    const name = c.country === "FR" ? c.product_name : c.brand_name;
    if (!name || name.length > 300 || c.name_only) return no("no_code");
    return { product: { country: c.country, name }, reason: null };
  }
  return no("country");
}

export function infoQuery(
  vocab: Loaded,
  item: Pick<Item, "candidate" | "choices">,
  language: Locale,
  demo: boolean,
): InfoQuery {
  const shown = candidateIngredients(vocab, item.candidate, item.choices);
  const ingredients: MedicineInfoIn["ingredients"] = [];
  const asked = shown.map((g) => {
    if (!g.key || g.notChecked || ingredients.length >= MAX_INGREDIENTS)
      return null;
    ingredients.push({ atc_codes: codesOf(g) });
    return ingredients.length - 1;
  });
  const { product, reason } = productOf(item.candidate, demo);
  const body: MedicineInfoIn | null =
    ingredients.length === 0 && !product
      ? null
      : { language, ingredients, ...(product ? { product } : {}) };
  return { shown, asked, body, noProduct: reason };
}

/** The key of one request, for the session cache. */
export const queryKey = (body: MedicineInfoIn): string => JSON.stringify(body);

"use client";
/**
 * Names shown on patient screens (experience design §8.3): the box name of an item, and the
 * ingredient names of its candidate by the note's rule (doctor-loop DP16), never raw Wikidata
 * labels in other languages.
 */
import type { Candidate } from "@/api/contracts";
import type { Item } from "@/store/list";
import { ingredientName, type IngredientName, type Loaded } from "@/vocabulary";

export interface ShownIngredient {
  position: number | null;
  key: string | null;
  name: IngredientName;
  codes: string[];
  combinationCode: boolean;
  /** For an ingredient that cannot be checked: the reason code (not_checked.<reason>). */
  notChecked: string | null;
  published: string | null;
}

export function candidateIngredients(
  v: Loaded,
  c: Candidate,
  choices: Item["choices"] = [],
): ShownIngredient[] {
  if (c.kind === "ingredient")
    return [
      {
        position: null,
        key: c.ingredient_key.qid,
        name: ingredientName(
          v,
          c.ingredient_key.qid,
          c.ingredient_key.label_en,
        ),
        codes: c.atc_codes.map((a) => a.code),
        combinationCode: false,
        notChecked: null,
        published: null,
      },
    ];
  return c.ingredients.map((g) => {
    const chosen =
      g.status === "ambiguous"
        ? choices.find((ch) => ch.position === g.position)?.ingredient
        : undefined;
    const key = g.ingredient_key?.qid ?? chosen ?? null;
    const name: IngredientName = key
      ? ingredientName(v, key, g.ingredient_key?.label_en ?? null)
      : { text: g.published_name, basis: "not_reviewed", tag: null };
    const notChecked = c.homeopathic
      ? "homeopathic_product"
      : g.status === "unmapped"
        ? (g.reason ?? "no_ingredient_key")
        : g.status === "ambiguous" && !chosen
          ? "ambiguous"
          : null;
    return {
      position: g.position,
      key,
      name,
      codes: g.atc_codes.map((a) => a.code),
      combinationCode: g.atc_selection === "component_code",
      notChecked,
      published: g.published_name,
    };
  });
}

/** The name of an ingredient key as shown, or its key when no name is known. */
export function keyName(
  v: Loaded,
  key: string,
  labelEn: string | null,
): string {
  return ingredientName(v, key, labelEn).text ?? key;
}

/** The box name of item `i`, else a placeholder. Box names never leave the browser. */
export function boxName(items: readonly Item[], i: number): string | null {
  return items[i]?.boxName || null;
}

/**
 * Synthetic group answers of the medicine-information route in the shape of the recorded demo
 * file (`Recorded`: language, then the sorted ATC codes of one ingredient joined with a space,
 * then the API's answer). Typed with the production types and decoded by the production decoder;
 * nothing is read from the recorded file.
 *
 * Two ingredients have a group sentence in every language (amlodipine, lisinopril); every other
 * code set is outside the covered groups (status "none").
 */
import * as D from "@/api/decode";
import { ingredient } from "@/plaininfo/model";
import type { Recorded } from "@/plaininfo/client";

type Ingredient = D.Infer<typeof ingredient>;

export const LANGUAGES = ["en", "tr", "de", "fr", "es", "pt"] as const;
export type Language = (typeof LANGUAGES)[number];

export const GROUPS_VERSION = "a".repeat(64);

/** The two covered ingredients: their ATC code, group id and group name. */
export const COVERED = {
  C08CA01: { id: "calcium_channel_blocker", name: "Calcium channel blockers" },
  C09AA03: { id: "ace_inhibitor", name: "ACE inhibitors" },
} as const;

const NONE: Ingredient = {
  status: "none",
  groups: [],
  other_uses: false,
  abrupt_stop: false,
};

/** The answer for one ingredient: a group sentence for a covered code, "none" for any other. */
export function answerOf(language: string, codesKey: string): Ingredient {
  const g = (COVERED as Record<string, { id: string; name: string }>)[codesKey];
  const out: Ingredient = g
    ? {
        status: "single",
        groups: [
          {
            id: g.id,
            name: `${g.name} (${language})`,
            text: `Synthetic sentence in ${language} for the group ${g.name}.`,
            codes: [codesKey],
            review_status: "not_reviewed",
          },
        ],
        other_uses: false,
        abrupt_stop: false,
      }
    : NONE;
  const r = D.decode(ingredient, out);
  if (!r.ok) throw new Error("synthetic fixture plain-info does not decode");
  return out;
}

/** A recorded-shaped file that answers the given code sets in every language. */
export function plainInfoRecorded(codeSets: readonly string[]): Recorded {
  const keys = [...new Set([...codeSets, ...Object.keys(COVERED)])];
  return {
    groups_version: GROUPS_VERSION,
    ingredients: Object.fromEntries(
      LANGUAGES.map((l) => [
        l,
        Object.fromEntries(keys.map((k) => [k, answerOf(l, k)])),
      ]),
    ),
  };
}

/**
 * fast-check arbitraries for the Passport list logic (tests only). Small pools make identities,
 * keys and months collide often, so merging and duplicate groups are exercised.
 */
import fc from "fast-check";

import {
  FORM_GROUPS,
  type Origin,
  type PassportItem,
  type StrengthCode,
} from "./model";

export const ORIGINS: Origin[] = [
  { region: "TR", country: "TR" },
  { region: "EU", country: "FR" },
  { region: "EU", country: "ES" },
  { region: "EU", country: "DE" },
  { region: "EU", country: null },
  { region: "US", country: "US" },
  { region: "OTHER", country: null },
];

const strength: fc.Arbitrary<StrengthCode> = fc.record({
  amount: fc.constantFrom("5000", "40000", "500", "0.5", "1000"),
  unit: fc.constantFrom("ug" as const, "IU" as const),
  basis: fc.constantFrom("unit" as const, "mL" as const, "g" as const),
});

export const itemArb = (
  keys: fc.Arbitrary<string>,
  names: fc.Arbitrary<string>,
) =>
  fc
    .record({
      demo: fc.boolean(),
      origin: fc.constantFrom(...ORIGINS),
      source: fc.oneof(
        fc.constant({ entered_by_name: true as const }),
        fc.record({
          source_id: fc.constantFrom("titck", "eu_fr_bdpm", "openfda_ndc"),
          snapshot_date: fc.constantFrom("2026-11-06", "2026-11-03"),
        }),
      ),
      code: fc.option(
        fc.record({
          kind: fc.constant("scan"),
          value: fc.constantFrom("A", "B"),
        }),
        { nil: null },
      ),
      boxName: names,
      ingredients: fc.array(
        fc.record({
          key: fc.option(keys, { nil: null, freq: 6 }),
          label: fc.constant("ingredient"),
          strength: fc.option(strength, { nil: null }),
          entered: fc.boolean(),
        }),
        { minLength: 0, maxLength: 3 },
      ),
      doseForm: fc.option(
        fc.record({
          group: fc.constantFrom(...FORM_GROUPS.slice(0, 3)),
          origin: fc.constantFrom("source" as const, "entered" as const),
        }),
        { nil: null },
      ),
      homeopathic: fc.integer({ min: 0, max: 6 }).map((n) => n === 0),
      boxes: fc.integer({ min: 1, max: 3 }),
      started: fc.option(fc.constantFrom("2023-01", "2024-02", "2024-03"), {
        nil: null,
      }),
    })
    .map((r): Omit<PassportItem, "id"> => ({
      ...r,
      ingredients: r.ingredients.map((i) => ({
        key: i.key,
        label: i.label,
        status: i.key ? "mapped" : "unmapped",
        strength: i.strength,
        strengthOrigin: i.strength ? (i.entered ? "entered" : "source") : null,
      })),
    }));

const SMALL_KEYS = fc.constantFrom("Q1", "Q2", "Q3", "Q4", "J1");
const SMALL_NAMES = fc.constantFrom(
  "Demo A",
  "demo a ",
  "Démo B",
  "DEMO B",
  "C",
);

/** A list with item ids unique within the list (`prefix` keeps them unique across lists). */
export const listArb = (
  prefix: string,
  opts: {
    keys?: fc.Arbitrary<string>;
    names?: fc.Arbitrary<string>;
    max?: number;
  } = {},
) =>
  fc
    .array(itemArb(opts.keys ?? SMALL_KEYS, opts.names ?? SMALL_NAMES), {
      maxLength: opts.max ?? 8,
    })
    .map((items): PassportItem[] =>
      items.map((item, i) => ({ ...item, id: `${prefix}${i}` })),
    );

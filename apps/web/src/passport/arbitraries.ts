/**
 * fast-check arbitraries for the Passport list logic (tests only). Small pools make identities,
 * keys and months collide often, so merging and duplicate groups are exercised.
 */
import fc from "fast-check";

import * as M from "./model";

import {
  FORM_GROUPS,
  type Origin,
  type PassportItem,
  type StrengthCode,
} from "./model";

const DISCLAIMER =
  "Janus provides information, not medical advice. Research prototype — not a medical device.";

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
          source_id: fc.constantFrom(
            "titck",
            "eu_fr_bdpm",
            "openfda_ndc",
            "eu_it_aifa",
          ),
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

// --- presence answers (codes only) ------------------------------------------------------
const cmpArb = fc.record({
  result: fc.constantFrom(...M.RESULTS),
  reason: fc.option(fc.constantFrom(...M.CMP_REASONS), { nil: null }),
  comparable: fc.nat(9),
  equal: fc.nat(9),
});
const keyArb = fc.integer({ min: 1, max: 999 }).map((n) => `Q${n}`);
const answerArb = fc.record({
  source: fc.nat(4),
  status: fc.constantFrom(...M.STATUSES),
  products: fc.nat(99),
  with_other_ingredients: fc.nat(99),
  keys_found: fc.array(keyArb, { maxLength: 3 }),
  homeopathic_left_out: fc.nat(9),
  comparison: fc.option(
    fc.record({
      strength: cmpArb,
      dose_form: cmpArb,
      strength_and_dose_form: cmpArb,
    }),
    { nil: null },
  ),
});
const sourceArb = fc.record({
  source: fc.nat(4),
  source_id: fc.option(fc.constantFrom(...M.SOURCE_IDS), { nil: null }),
  region: fc.constantFrom(...M.SOURCE_REGIONS),
  country: fc.option(fc.constantFrom(...M.SOURCE_COUNTRIES), { nil: null }),
  status: fc.constantFrom("loaded" as const, "source_unavailable" as const),
  reason: fc.option(fc.constantFrom(...M.UNAVAILABLE_REASONS), { nil: null }),
  snapshot_date: fc.option(fc.constantFrom("2026-11-06", "2026-11-03"), {
    nil: null,
  }),
  stale: fc.boolean(),
  attribution: fc.option(fc.constantFrom(...M.ATTRIBUTIONS), { nil: null }),
  as_published: fc.boolean(),
  can_compare: fc.record({ strength: fc.boolean(), dose_form: fc.boolean() }),
});
export const presenceOutArb = fc.record({
  dataset_version: fc.constant("a".repeat(64)),
  form_table_version: fc.constant("b".repeat(64)),
  sources: fc.array(sourceArb, { minLength: 5, maxLength: 5 }),
  items: fc.array(
    fc.record({
      item: fc.nat(49),
      keys: fc.array(keyArb, { minLength: 1, maxLength: 3 }),
      unknown_keys: fc.array(keyArb, { maxLength: 1 }),
      answers: fc.array(answerArb, { minLength: 5, maxLength: 5 }),
    }),
    { maxLength: 4 },
  ),
  notices: fc.subarray([...M.NOTICES]),
  disclaimer: fc.constant(DISCLAIMER),
});

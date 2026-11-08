/**
 * Shared fast-check arbitraries (experience design §17). Shapes follow the recorded fixtures.
 */
import fc from "fast-check";

export const digit = fc.constantFrom(..."0123456789");
export const digits = (n: number) =>
  fc.array(digit, { minLength: n, maxLength: n }).map((d) => d.join(""));

export const qid = fc.oneof(
  fc.integer({ min: 1, max: 999_999_999 }).map((n) => `Q${n}`),
  fc.integer({ min: 1, max: 99_999 }).map((n) => `J${n}`),
);

export const candidateId = fc
  .tuple(
    fc.constantFrom("TR", "US", "EU"),
    fc.constantFrom("titck", "openfda_ndc", "eu_fr_bdpm", "eu_es_cima"),
    fc.integer({ min: 0, max: 999_999_999 }),
  )
  .map(([r, s, n]) => `${r}:${s}:${n}`);

export const hex64 = fc
  .array(fc.constantFrom(..."0123456789abcdef"), {
    minLength: 64,
    maxLength: 64,
  })
  .map((a) => a.join(""));

export const month = fc
  .tuple(fc.integer({ min: 1990, max: 2026 }), fc.integer({ min: 1, max: 12 }))
  .map(([y, m]) => `${y}-${String(m).padStart(2, "0")}`);

export const eventKey = fc.constantFrom(
  "peripheral_oedema",
  "cough",
  "constipation",
  "depression",
  "rash",
  "arrhythmia",
  "gastric_ulcer_bleed",
);

/** A box name that must never reach a request body (P2, P4). */
export const sentinelBoxName = fc
  .string({ minLength: 1, maxLength: 20 })
  .map((s) => `ZZBOX${s.replace(/\s/g, "")}`);

/** An ATC-code-shaped string (levels 3 to 5; level 2 "C08" is indistinguishable from a QID). */
export const atcLike = fc.constantFrom(
  "C08CA01",
  "C09BB03",
  "N06AB06",
  "C03C",
  "A02BC",
  "M01AE01",
);
export const ATC_SHAPE = /\b[ABCDGHJLMNPRSV][0-9]{2}[A-Z]{1,2}([0-9]{2})?\b/;

/** Every string value and every key of a JSON value. */
export function walk(
  value: unknown,
  keys: string[] = [],
  strings: string[] = [],
) {
  if (typeof value === "string") strings.push(value);
  else if (Array.isArray(value)) for (const v of value) walk(v, keys, strings);
  else if (value && typeof value === "object")
    for (const [k, v] of Object.entries(value)) {
      keys.push(k);
      walk(v, keys, strings);
    }
  return { keys, strings };
}

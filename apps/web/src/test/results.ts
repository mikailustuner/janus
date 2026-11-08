/**
 * Shape-true arbitraries of API responses, derived from the recorded fixtures (design §17).
 */
import type {
  CascadeResult,
  EvidenceResolution,
  Finding,
  NoteOut,
  PairOut,
} from "@/api/contracts";
import * as D from "@/api/decode";
import cologne from "@/demo/fixtures/cologne.json";
import istanbul from "@/demo/fixtures/istanbul.json";
import ohio from "@/demo/fixtures/ohio.json";
import en from "@/vocabulary/en.json";
import index from "@/vocabulary/index.json";
import type { Loaded, Vocabulary, VocabularyIndex } from "@/vocabulary";

import { fc } from "./fc";

const decode = <T>(d: D.Decoder<T>, v: unknown): T => {
  const r = D.decode(d, v);
  if (!r.ok) throw new Error(r.path);
  return r.value;
};

export const FIXTURES = [istanbul, cologne, ohio] as const;
export const RESULTS = FIXTURES.map((f) =>
  decode(D.cascadeResult, f.evaluation),
);
export const FINDINGS: Finding[] = RESULTS.flatMap((r) => r.findings);
export const EVIDENCE: EvidenceResolution[] = FIXTURES.flatMap((f) =>
  Object.values(f.evidence).map((e) => decode(D.evidenceResolution, e)),
);
export const PAIRS: PairOut[] = FIXTURES.flatMap((f) =>
  Object.values(f.memory.pairs).map((p) => decode(D.pairOut, p)),
);
export const NOTES: Record<string, NoteOut>[] = FIXTURES.map((f) =>
  Object.fromEntries(
    Object.entries(f.notes).map(([k, v]) => [k, decode(D.noteOut, v)]),
  ),
);

export const VOCAB_EN: Loaded = {
  locale: "en",
  vocab: en as unknown as Vocabulary,
  index: index as unknown as VocabularyIndex,
};

const REASONS = [
  "homeopathic_product",
  "ambiguous",
  "no_ingredient_key",
  "possible_unsplit_combination",
  "no_ingredient_atc",
  "no_ingredient_atc_for_route",
] as const;

/** A CascadeResult with 0–8 findings drawn from the recorded ones, re-indexed onto n items. */
export const cascadeResultArb = fc
  .record({
    base: fc.constantFrom(...RESULTS),
    n: fc.integer({ min: 2, max: 15 }),
    picks: fc.array(
      fc.record({
        f: fc.constantFrom(...FINDINGS),
        formConfirmed: fc.boolean(),
        i: fc.nat(),
        j: fc.nat(),
        locator: fc.boolean(),
      }),
      { maxLength: 8 },
    ),
    warnings: fc.array(fc.nat(), { maxLength: 5 }),
    notChecked: fc.array(
      fc.record({
        item: fc.nat(),
        position: fc.nat({ max: 3 }),
        reason: fc.constantFrom(...REASONS),
      }),
      { maxLength: 4 },
    ),
    statement: fc.constantFrom(
      "none",
      "no_pattern_found",
      "rule_base_unavailable",
    ),
    truncated: fc.boolean(),
  })
  .map(
    ({
      base,
      n,
      picks,
      warnings,
      notChecked,
      statement,
      truncated,
    }): CascadeResult => {
      const findings = picks.map((p, k) => ({
        ...p.f,
        finding_id: `${p.f.finding_id}:${k}`,
        form_confirmed: p.formConfirmed,
        index: {
          ...p.f.index,
          items: [p.i % n],
          form_confirmed: p.formConfirmed || p.f.index.form_confirmed,
        },
        marker: { ...p.f.marker, items: [p.j % n] },
        faers_locator: p.locator ? p.f.faers_locator : null,
      }));
      return {
        ...base,
        findings:
          statement === "none"
            ? findings
            : statement === "no_pattern_found"
              ? []
              : [],
        item_warnings: warnings.map((w) => ({
          item: w % n,
          ingredient_key: "Q1",
          code: "do_not_stop_suddenly" as const,
          text: "Do not stop this medicine suddenly.",
        })),
        not_checked: notChecked.map((x) => ({ ...x, item: x.item % n })),
        statement:
          statement === "none"
            ? null
            : {
                code: statement as "no_pattern_found" | "rule_base_unavailable",
                text: "canonical",
              },
        notices: truncated ? ["chains_truncated"] : [],
        same_product: [
          { rule_id: "pipc:5", index_key: "Q1", marker_key: "Q2", items: [0] },
        ],
      };
    },
  )
  .chain((r) =>
    fc.constant({
      result: r,
      n: Math.max(
        2,
        ...r.findings
          .flatMap((f) => [...f.index.items, ...f.marker.items])
          .map((x) => x + 1),
        ...r.item_warnings.map((w) => w.item + 1),
      ),
    }),
  );

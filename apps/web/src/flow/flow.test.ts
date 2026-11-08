// Feature: experience, Properties P3 (evaluation input), P23 (timeline), P6 (locator),
// P7 (findings view model), P9 (safety lines), P30 (evidence view model).
import { describe, expect, it } from "vitest";

import {
  candidateId,
  hex64,
  month,
  qid,
  sentinelBoxName,
  walk,
  ATC_SHAPE,
} from "@/test/arbitraries";
import { check, fc } from "@/test/fc";
import { cascadeResultArb, EVIDENCE, FINDINGS, VOCAB_EN } from "@/test/results";
import type { Item } from "@/store/list";

import { currentMonth, MAX_ITEMS, monthInput, toEvaluateIn } from "./evaluate";
import { resultsView } from "./findings";
import { evidenceView } from "./integrity";
import { eventKeyOf, formatLocator, parseLocator } from "./locator";
import { timeline } from "./timeline";

const NOW = new Date(2026, 10, 8);
const source = {
  source_id: "titck",
  run_id: "r",
  region: "TR",
  snapshot_date: "2026-11-06",
};

const itemArb = (dv: string) =>
  fc
    .record({
      kind: fc.constantFrom("product", "ingredient"),
      id: candidateId,
      key: qid,
      started: fc.option(
        month.filter((m) => m <= "2026-11"),
        { nil: null },
      ),
      boxName: sentinelBoxName,
      ambiguousChoice: fc.option(qid, { nil: undefined }),
    })
    .map((x): Item => ({
      id: "x",
      sourceKey: { kind: "scan", content: "x" },
      datasetVersion: dv,
      candidate:
        x.kind === "ingredient"
          ? {
              kind: "ingredient",
              matched_by: "name",
              score: null,
              ingredient_key: { qid: x.key, label_en: "x", labels: {} },
              atc_codes: [{ code: "C08CA01", source, product: null }],
              atc_selection: "all_codes",
              rxcuis: [],
              rxcui_status: "from_wikidata",
              source,
            }
          : {
              kind: "product",
              candidate_id: x.id,
              region: "TR",
              country: null,
              matched_by: "barcode",
              score: null,
              product_name: x.boxName,
              brand_name: null,
              generic_name: null,
              ingredient_text: null,
              published_atc: "C09BB03",
              product_type: null,
              routes: [],
              dosage_form: null,
              marketing_end_date: null,
              suspension_status: null,
              name_only: false,
              homeopathic: false,
              status_published: [],
              product_rxcuis: [],
              packages: [],
              source,
              ingredients: [
                {
                  position: 0,
                  published_name: "a",
                  strength: null,
                  status: "ambiguous",
                  reason: null,
                  ingredient_key: null,
                  key_candidates: x.ambiguousChoice ? [x.ambiguousChoice] : [],
                  match_step: null,
                  atc_codes: [],
                  atc_selection: null,
                  rxcuis: [],
                  rxcui_status: null,
                  source,
                },
              ],
            },
      choices: x.ambiguousChoice
        ? [
            { position: 0, ingredient: x.ambiguousChoice },
            { position: 3, ingredient: x.key },
          ]
        : [],
      started: x.started,
      boxName: x.boxName,
      needsConfirmation: false,
    }));

describe("P3 evaluation input", () => {
  it("keeps list order, one kind per item, valid choices and months, no box name or ATC code", () => {
    check(
      fc.property(
        hex64.chain((dv) =>
          fc.array(itemArb(dv), { minLength: 1, maxLength: 60 }),
        ),
        (items) => {
          const r = toEvaluateIn(items, NOW);
          if (items.length > MAX_ITEMS) {
            expect(r).toEqual({ ok: false, reason: "too_many" });
            return;
          }
          expect(r.ok).toBe(true);
          if (!r.ok) return;
          expect(r.body.items).toHaveLength(items.length);
          r.body.items.forEach((b, i) => {
            const c = items[i]!.candidate;
            if (c.kind === "product") expect(b.product).toBe(c.candidate_id);
            else expect(b.ingredient).toBe(c.ingredient_key.qid);
            expect(b.started ?? null).toBe(items[i]!.started);
            for (const ch of b.choices ?? []) {
              expect(ch.position).toBe(0); // only ambiguous positions, with a listed key
            }
          });
          const { strings, keys } = walk(r.body);
          for (const s of strings) {
            expect(ATC_SHAPE.test(s)).toBe(false);
            expect(items.some((i) => s.includes(i.boxName))).toBe(false);
          }
          expect(keys).not.toContain("demo");
        },
      ),
    );
  });
  it("refuses mixed dataset versions, items needing confirmation and future months", () => {
    check(
      fc.property(hex64, hex64, (a, b) => {
        fc.pre(a !== b);
        const [x, y] = fc.sample(itemArb(a), 2) as [Item, Item];
        expect(toEvaluateIn([x, { ...y, datasetVersion: b }], NOW)).toEqual({
          ok: false,
          reason: "mixed_versions",
        });
        expect(toEvaluateIn([{ ...x, needsConfirmation: true }], NOW).ok).toBe(
          false,
        );
        expect(toEvaluateIn([{ ...x, started: "2026-12" }], NOW)).toEqual({
          ok: false,
          reason: "future_start",
        });
      }),
      { numRuns: 20 },
    );
    expect(toEvaluateIn([], NOW)).toEqual({ ok: false, reason: "empty" });
  });
  it("maps 'since when' input across year ends and refuses the future", () => {
    check(
      fc.property(
        fc.date({
          min: new Date(2000, 0, 1),
          max: new Date(2040, 0, 1),
          noInvalidDate: true,
        }),
        fc.integer({ min: 1990, max: 2045 }),
        fc.integer({ min: 1, max: 12 }),
        (now, year, m) => {
          const r = monthInput({ dontKnow: false, year, month: m }, now);
          const started = `${year}-${String(m).padStart(2, "0")}`;
          if (started > currentMonth(now))
            expect(r).toEqual({ ok: false, reason: "future" });
          else expect(r).toEqual({ ok: true, started });
          expect(monthInput({ dontKnow: true }, now)).toEqual({
            ok: true,
            started: null,
          });
        },
      ),
    );
  });
});

describe("P23 timeline", () => {
  it("orders dated items stably, lanes the undated ones, draws each finding once", () => {
    check(
      fc.property(
        cascadeResultArb,
        fc.array(fc.option(month, { nil: null }), {
          minLength: 15,
          maxLength: 15,
        }),
        ({ result, n }, starts) => {
          const items = starts
            .slice(0, Math.max(n, 2))
            .map((started) => ({ started }));
          while (items.length < n) items.push({ started: null });
          const m = timeline(items, result);
          for (let k = 1; k < m.dated.length; k++) {
            const [a, b] = [m.dated[k - 1]!, m.dated[k]!];
            expect(
              a.started < b.started ||
                (a.started === b.started && a.item < b.item),
            ).toBe(true);
          }
          expect(
            new Set([...m.dated.map((d) => d.item), ...m.undated]).size,
          ).toBe(items.length);
          expect(m.undated.every((i) => items[i]!.started === null)).toBe(true);
          expect(m.links.map((l) => l.findingId)).toEqual(
            result.findings.map((f) => f.finding_id),
          );
          m.links.forEach((l, k) =>
            expect(l.months).toBe(result.findings[k]!.months_between),
          );
        },
      ),
    );
  });
});

describe("P6 locator", () => {
  const parts = fc.record({
    ingredient: qid,
    event: fc.constantFrom("cough", "peripheral_oedema", "a.b-c_d"),
    region: fc.constantFrom("ALL", "TR", "EU", "US", "OTHER", "UNKNOWN"),
    scope: fc.constantFrom("suspect", "any"),
  });
  it("parses what it formats and refuses mutations", () => {
    check(
      fc.property(
        parts,
        fc.nat(),
        fc.string({ minLength: 1, maxLength: 3 }),
        (p, at, junk) => {
          const s = formatLocator(p);
          expect(parseLocator(s)).toEqual(p);
          const cut = at % s.length;
          const mutated = s.slice(0, cut) + junk + s.slice(cut + 1);
          if (mutated !== s && parseLocator(mutated)) {
            // a mutation inside a value can still be a valid locator; it then parses consistently
            expect(formatLocator(parseLocator(mutated)!)).toBe(mutated);
          }
        },
      ),
    );
    expect(parseLocator(null)).toBeNull();
    expect(
      parseLocator("faers:ingredient=C08CA01;event=x;region=ALL;scope=suspect"),
    ).toBeNull();
  });
  it("takes the event key from the locator, else from the rule row", () => {
    for (const f of FINDINGS) {
      expect(eventKeyOf(f, VOCAB_EN)).toBe(
        parseLocator(f.faers_locator)?.event,
      );
      expect(eventKeyOf({ ...f, faers_locator: null }, VOCAB_EN)).toBe(
        parseLocator(f.faers_locator)!.event,
      );
    }
  });
});

describe("P7 / P9 findings view model and safety lines", () => {
  it("puts each finding in exactly one group, keeps API order, never same_product", () => {
    check(
      fc.property(cascadeResultArb, ({ result }) => {
        const v = resultsView(result, VOCAB_EN);
        if (result.statement?.code === "rule_base_unavailable") {
          expect(v).toEqual({ kind: "unavailable" });
          return;
        }
        if (v.kind !== "ok") throw new Error("ok expected");
        const ids = [...v.confirmed, ...v.unconfirmed].map(
          (f) => f.finding.finding_id,
        );
        expect(new Set(ids).size).toBe(result.findings.length);
        expect(v.confirmed.every((f) => f.finding.form_confirmed)).toBe(true);
        expect(v.unconfirmed.every((f) => !f.finding.form_confirmed)).toBe(
          true,
        );
        for (const g of [v.confirmed, v.unconfirmed])
          for (let k = 1; k < g.length; k++)
            expect(g[k - 1]!.position).toBeLessThan(g[k]!.position);
        expect(ids.some((id) => id.startsWith("same_product"))).toBe(false);
        expect(v.warnedItems).toEqual(
          [...new Set(result.item_warnings.map((w) => w.item))].sort(
            (a, b) => a - b,
          ),
        );
        expect(v.notChecked).toHaveLength(result.not_checked.length);
        expect(v.cannotCheck).toHaveLength(
          result.rules.not_matchable.length + result.rules.disabled.length,
        );
        expect(v.noPattern).toBe(result.statement?.code === "no_pattern_found");
        // P9: every shown event with a safety line has it, and the emergency notice comes first.
        for (const f of [...v.confirmed, ...v.unconfirmed]) {
          const line = f.eventKey
            ? (VOCAB_EN.vocab.events[f.eventKey]?.safety_line ?? null)
            : null;
          expect(f.safetyLine).toBe(line);
          if (line) expect(v.safetyLines).toContain(line);
        }
        expect(v.emergencyFirst).toBe(v.safetyLines.length > 0);
        expect(v.chainsTruncated).toBe(
          result.notices.includes("chains_truncated"),
        );
      }),
    );
  });
  it("gives the crisis line for a depression finding (PIPC row 3)", () => {
    const f = { ...FINDINGS[0]!, rule_id: "pipc:3", faers_locator: null };
    const v = resultsView(
      { ...RESULT0(), statement: null, findings: [f] },
      VOCAB_EN,
    );
    if (v.kind !== "ok") throw new Error();
    expect(v.safetyLines).toEqual(["crisis_support"]);
  });
});

function RESULT0() {
  return fc.sample(cascadeResultArb, 1)[0]!.result;
}

describe("P30 evidence view model", () => {
  it("never stamps a used source and says 'no retracted source used' iff the line says so", () => {
    const retracted = (r: (typeof EVIDENCE)[number]) => ({
      ...r,
      items: r.items.map((i, k) =>
        k === 0
          ? {
              ...i,
              citable: false,
              exclusion_reason: "retracted" as const,
              integrity: i.integrity && {
                ...i.integrity,
                status: "retracted" as const,
              },
            }
          : i,
      ),
      excluded: [{ id: r.items[0]!.id, reason: "retracted" as const }],
      line: {
        ...r.line,
        no_retracted_used: false,
        excluded: [{ id: r.items[0]!.id, reason: "retracted" as const }],
      },
    });
    check(
      fc.property(
        fc.constantFrom(...EVIDENCE),
        fc.boolean(),
        (base, withRetraction) => {
          const r = withRetraction ? retracted(base) : base;
          const v = evidenceView(r);
          expect(
            v.used.some(
              (i) => i.integrity?.status === "retracted" || i.exclusion_reason,
            ),
          ).toBe(false);
          for (const e of v.excluded)
            if (e.stamp) expect(v.used.map((i) => i.id)).not.toContain(e.id);
          expect(v.noRetracted).toBe(r.line.no_retracted_used);
          expect(v.exceptions).toEqual(r.line.excluded);
          if (withRetraction)
            expect(v.excluded.some((e) => e.stamp)).toBe(true);
        },
      ),
    );
  });
});

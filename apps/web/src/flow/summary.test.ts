// Feature: janus-report, Properties P1, P3, P5 (design §6): every finding is in exactly one timing
// group; the medicine, region and source counts add up to the list; the integrity summary never
// says "no retracted source" unless every line says so.
import { describe, expect, it } from "vitest";

import type { EvidenceResolution } from "@/api/contracts";
import { check, fc } from "@/test/fc";
import { EVIDENCE, VOCAB_EN } from "@/test/results";
import { summaryInputArb } from "@/test/summary";

import { ORDER_GROUPS, orderGroup, resultsView } from "./findings";
import { BOX_REGIONS, integritySummary, summaryView } from "./summary";

describe("summaryView", () => {
  it("P1: every finding is in exactly one timing group, the group of its timing", () => {
    check(
      fc.property(summaryInputArb, ({ r, items }) => {
        const v = summaryView(r, items, VOCAB_EN);
        if (r.statement?.code === "rule_base_unavailable") {
          expect(v.kind).toBe("unavailable");
          return;
        }
        if (v.kind !== "ok") throw new Error("expected ok");
        const grouped = ORDER_GROUPS.flatMap((g) =>
          v.patterns.groups[g].map((f) => ({ g, f })),
        );
        expect(grouped.length).toBe(r.findings.length);
        expect(v.patterns.total).toBe(r.findings.length);
        const positions = grouped
          .map(({ f }) => f.position)
          .sort((a, b) => a - b);
        expect(positions).toEqual(r.findings.map((_, i) => i));
        for (const { g, f } of grouped)
          expect(g).toBe(orderGroup(r.findings[f.position]!.timing));
        expect(v.patterns.unconfirmedForm).toBe(
          r.findings.filter((f) => !f.form_confirmed).length,
        );
      }),
    );
  });

  it("P2 (model): the abrupt-stop count is the number of distinct warned items", () => {
    check(
      fc.property(summaryInputArb, ({ r, items }) => {
        const v = summaryView(r, items, VOCAB_EN);
        const rv = resultsView(r, VOCAB_EN);
        if (v.kind !== "ok" || rv.kind !== "ok") return;
        const distinct = new Set(r.item_warnings.map((w) => w.item));
        expect(v.warnedItems.length).toBe(distinct.size);
        expect(v.warnedItems).toEqual(rv.warnedItems);
      }),
    );
  });

  it("P3: medicines, regions and sources add up to the list", () => {
    check(
      fc.property(summaryInputArb, ({ r, items }) => {
        const v = summaryView(r, items, VOCAB_EN);
        if (v.kind !== "ok") return;
        expect(v.medicines.total).toBe(items.length);
        expect(v.medicines.notFully).toEqual(
          [
            ...new Set(
              r.not_checked.map((n) => n.item).filter((i) => i < items.length),
            ),
          ].sort((a, b) => a - b),
        );
        const regions = BOX_REGIONS.reduce((s, k) => s + v.regions[k], 0);
        expect(regions).toBe(items.length);
        expect(v.sources.reduce((s, x) => s + x.items, 0)).toBe(items.length);
        for (const s of v.sources)
          expect(s.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(v.month).toBe(r.as_of_month);
      }),
    );
  });

  it("the no-pattern flag follows the statement", () => {
    check(
      fc.property(summaryInputArb, ({ r, items }) => {
        const v = summaryView(r, items, VOCAB_EN);
        if (v.kind !== "ok") return;
        expect(v.noPattern).toBe(
          r.findings.length === 0 && r.statement?.code === "no_pattern_found",
        );
      }),
    );
  });
});

const resolutionArb = fc
  .record({
    base: fc.constantFrom(...EVIDENCE),
    noRetracted: fc.boolean(),
    excluded: fc.boolean(),
  })
  .map(({ base, noRetracted, excluded }): EvidenceResolution => ({
    ...base,
    line: {
      ...base.line,
      no_retracted_used: noRetracted,
      excluded: excluded ? [{ id: "x", reason: "retracted" }] : [],
    },
  }));

describe("integritySummary", () => {
  it("P5: no retracted source only if every line says so; sources are distinct used ids", () => {
    check(
      fc.property(fc.array(resolutionArb, { maxLength: 6 }), (rs) => {
        const s = integritySummary(rs);
        expect(s.noRetracted).toBe(
          rs.length > 0 && rs.every((r) => r.line.no_retracted_used),
        );
        expect(s.withExclusions).toBe(
          rs.filter((r) => r.line.excluded.length).length,
        );
        const ids = new Set(
          rs.flatMap((r) =>
            r.items
              .filter(
                (i) =>
                  !i.exclusion_reason &&
                  i.integrity?.status !== "retracted" &&
                  !r.excluded.some((e) => e.id === i.id),
              )
              .map((i) => i.id),
          ),
        );
        expect(s.sources).toBe(ids.size);
      }),
    );
  });
});

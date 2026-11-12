// research-tools properties R1-R6 (design §5): the recorded datasets decode; the data-quality
// counts and filters partition the findings; evidence links stay on the two report hosts; no
// TİTCK barcode reaches the page model; the onset table shows statistics only where the design
// allows them, and sorting is a stable permutation that keeps rows without a median last.
import fc from "fast-check";
import { describe, expect, it } from "vitest";

import * as D from "@/api/decode";

import dqFx from "./data-quality.recorded.json";
import {
  classStatusCounts,
  CLASSES,
  dataQualityReport,
  demoDataQuality,
  evidenceLink,
  filterFindings,
  STATUSES,
  whoccGroup,
  type Filter,
  type Finding,
} from "./dataQuality";
import onsetFx from "./faers-onset.recorded.json";
import {
  demoOnset,
  CAVEATS,
  ONSET_STATUSES,
  onsetTable,
  showsMedian,
  showsShape,
  showsStatistics,
  sortRows,
  type OnsetRow,
  type SortKey,
} from "./onset";

const dq = D.decode(dataQualityReport, dqFx.report);
const onset = D.decode(onsetTable, onsetFx.table);
if (!dq.ok || !onset.ok) throw new Error("recorded fixtures do not decode");
const report = dq.value;
const table = onset.value;

const filterArb: fc.Arbitrary<Filter> = fc.record({
  klass: fc.constantFrom("all" as const, ...CLASSES),
  status: fc.constantFrom("all" as const, ...STATUSES),
  query: fc.oneof(
    fc.constant(""),
    fc.constantFrom(...report.findings.map((f) => f.code.slice(0, 3))),
    fc.string({ maxLength: 6 }),
  ),
});

describe("data-quality report (R1-R3)", () => {
  it("R1: class × status counts sum to the findings and match the report summary", () => {
    const c = classStatusCounts(report.findings);
    for (const k of CLASSES)
      expect(STATUSES.reduce((s, x) => s + c[k][x], 0)).toBe(
        report.summary.by_class[k],
      );
    for (const s of STATUSES)
      expect(CLASSES.reduce((n, k) => n + c[k][s], 0)).toBe(
        report.summary.by_status[s],
      );
    expect(report.findings).toHaveLength(report.summary.findings);
  });

  it("R2: a filter keeps exactly the matching findings, whatever their order", () => {
    fc.assert(
      fc.property(
        filterArb,
        fc.shuffledSubarray(report.findings, {
          minLength: report.findings.length,
        }),
        (f, shuffled) => {
          const a = filterFindings(report.findings, f);
          const b = filterFindings(shuffled, f);
          expect(b.map((x) => x.id)).toEqual(a.map((x) => x.id));
          for (const x of a) {
            if (f.klass !== "all") expect(x.class).toBe(f.klass);
            if (f.status !== "all") expect(x.status).toBe(f.status);
          }
          if (!f.query) {
            const all = report.findings.filter(
              (x) =>
                (f.klass === "all" || x.class === f.klass) &&
                (f.status === "all" || x.status === f.status),
            );
            expect(a).toHaveLength(all.length);
          }
        },
      ),
      { numRuns: 200 },
    );
  });

  it("R2: the class filters partition the findings", () => {
    const parts = CLASSES.map(
      (klass) =>
        filterFindings(report.findings, { klass, status: "all", query: "" })
          .length,
    );
    expect(parts.reduce((a, b) => a + b, 0)).toBe(report.findings.length);
  });

  it("R3: evidence links only on https Wikidata and WHOCC addresses", () => {
    fc.assert(
      fc.property(fc.webUrl({ withQueryParameters: true }), (url) => {
        const host = new URL(url).hostname;
        const ok = ["www.wikidata.org", "atcddd.fhi.no"].includes(host);
        expect(evidenceLink(url) !== null).toBe(ok && url.startsWith("https:"));
      }),
    );
    for (const bad of [
      "javascript:alert(1)",
      "http://www.wikidata.org/wiki/Q1",
      "https://www.wikidata.org.evil.example/wiki/Q1",
      "data:text/html,x",
      "",
      null,
    ])
      expect(evidenceLink(bad)).toBeNull();
    for (const f of report.findings) {
      if (f.wikidata_url) expect(evidenceLink(f.wikidata_url)).not.toBeNull();
      for (const u of f.whocc_group_urls) {
        expect(evidenceLink(u)).not.toBeNull();
        expect(whoccGroup(u)).toMatch(/^[A-Z]\d{2}[A-Z]{2}$/);
      }
    }
  });

  it("R3: no TİTCK barcode or GTIN in the recorded files the page can show", () => {
    const text = JSON.stringify(dqFx);
    expect(text).not.toMatch(/(?<!\d)869\d{10}(?!\d)/);
    expect(text).not.toMatch(/(?<!\d)0?869\d{10}(?!\d)/);
    // The decoded model keeps only the documented fields of a finding.
    const keys = new Set(
      report.findings.flatMap((f: Finding) => Object.keys(f)),
    );
    expect([...keys].sort()).toEqual(
      [
        "check",
        "class",
        "class_changed_from",
        "code",
        "compared_codes",
        "how_to_find",
        "id",
        "key",
        "label_en",
        "other_keys",
        "products",
        "reasons",
        "source",
        "status",
        "upstream",
        "whocc_group_urls",
        "wikidata_url",
      ].sort(),
    );
  });

  it("demo client answers from the file and downloads it verbatim", async () => {
    const c = demoDataQuality(dqFx);
    const r = await c.report();
    expect(r.ok).toBe(true);
    const csv = decodeURIComponent(
      c.download("csv").split(",").slice(1).join(","),
    );
    expect(csv).toBe(dqFx.csv);
    expect(c.download("md")).toMatch(/^data:text\/markdown/);
  });
});

const rowArb = fc.constantFrom(...table.rows);
const keyArb = fc.constantFrom<SortKey>(
  "position",
  "reports",
  "interval",
  "median",
  "status",
);

describe("FAERS onset table (R4-R6)", () => {
  it("R4: one row per PIPC position 1-65 with the fixed framing fields", () => {
    expect(table.rows.map((r) => r.pipc_position)).toEqual(
      Array.from({ length: 65 }, (_, i) => i + 1),
    );
    for (const r of table.rows) {
      expect(r.descriptive_only).toBe(true);
      expect(r.causal).toBe(false);
      expect(r.incidence).toBe(false);
      expect(r.counts_are).toBe("reports");
      expect(r.reports_with_interval).toBeLessThanOrEqual(r.candidate_reports);
    }
  });

  it("R5: statistics only for described and small-sample rows; shape only for described", () => {
    fc.assert(
      fc.property(rowArb, fc.constantFrom(...ONSET_STATUSES), (r, status) => {
        const row = { ...r, status } as OnsetRow;
        expect(showsStatistics(row)).toBe(
          status === "described" || status === "small_sample",
        );
        if (status !== "described") expect(showsShape(row)).toBe(false);
      }),
    );
    for (const r of table.rows)
      if (r.reports_with_interval < 10) expect(showsStatistics(r)).toBe(false);
  });

  it("R6: sorting is a permutation, stable on ties, rows without a median last", () => {
    fc.assert(
      fc.property(
        keyArb,
        fc.constantFrom("ascending" as const, "descending" as const),
        fc.shuffledSubarray(table.rows, { minLength: table.rows.length }),
        (key, dir, rows) => {
          const out = sortRows(rows, key, dir);
          expect(out.map((r) => r.pipc_position).sort((a, b) => a - b)).toEqual(
            rows.map((r) => r.pipc_position).sort((a, b) => a - b),
          );
          // Same result whatever the input order (ties broken by PIPC position).
          expect(out).toEqual(sortRows(table.rows, key, dir));
          if (key === "median") {
            const comparable = (r: OnsetRow) =>
              showsMedian(r) && !r.median_reflects_zero_heaping;
            const firstWithout = out.findIndex((r) => !comparable(r));
            if (firstWithout >= 0)
              for (const r of out.slice(firstWithout))
                expect(comparable(r)).toBe(false);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it("R5: a median is shown only with both bounds of its exact interval", () => {
    fc.assert(
      fc.property(rowArb, fc.boolean(), fc.boolean(), (r, lo, hi) => {
        const row = {
          ...r,
          median_exact_ci_low_days: lo ? r.median_exact_ci_low_days : null,
          median_exact_ci_high_days: hi ? r.median_exact_ci_high_days : null,
        };
        if (showsMedian(row)) {
          expect(showsStatistics(row)).toBe(true);
          expect(row.median_exact_ci_low_days).not.toBeNull();
          expect(row.median_exact_ci_high_days).not.toBeNull();
        }
      }),
    );
  });

  it("every dataset caveat has a translated short form, in every locale", async () => {
    expect([...CAVEATS].sort()).toEqual(Object.keys(table.caveats).sort());
    for (const l of ["en", "tr", "de", "fr", "es", "pt"]) {
      const m = (await import(`../../messages/${l}.json`)).default as {
        Onset: { caveats: Record<string, string> };
      };
      for (const c of CAVEATS)
        expect(m.Onset.caveats[c], `${l} ${c}`).toBeTruthy();
    }
  });

  it("demo client: every position answers its row, an unknown one is 404", async () => {
    const c = demoOnset(onsetFx);
    for (const r of table.rows) {
      const a = await c.row(r.pipc_position);
      expect(a.ok && a.data.row.pipc_position).toBe(r.pipc_position);
    }
    const none = await c.row(66);
    expect(!none.ok && none.error.messageKey).toBe("Onset.errors.unknown");
  });
});

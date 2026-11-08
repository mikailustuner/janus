// Feature: light-face, Property P16: rank text, CSV round trip, decoders (design §10, §11).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { decode } from "@/api/decode";
import { messageKeyFor } from "@/api/errors";

import {
  cardsOut,
  exportOut,
  overviewOut,
  validationOut,
  type ExportRow,
} from "./model";
import {
  CSV_COLUMNS,
  fileName,
  nameIn,
  parseCsv,
  rankText,
  toCsv,
} from "./view";

const fixture = JSON.parse(
  readFileSync(join(import.meta.dirname, "fixture.recorded.json"), "utf8"),
) as {
  overview: unknown;
  cards: Record<string, unknown>;
  validation: unknown;
  export: unknown;
};

describe("decoders", () => {
  it("accept the answers recorded from the real API", () => {
    expect(decode(overviewOut, fixture.overview).ok).toBe(true);
    for (const v of Object.values(fixture.cards))
      expect(decode(cardsOut, v).ok).toBe(true);
    expect(decode(validationOut, fixture.validation).ok).toBe(true);
    expect(decode(exportOut, fixture.export).ok).toBe(true);
  });

  it("reject an answer with a wrong or missing field", () => {
    const base = fixture.overview as Record<string, unknown>;
    fc.assert(
      fc.property(
        fc.constantFrom(
          "status",
          "review_status",
          "snapshot",
          "disclaimer",
          "top_k",
          "goals",
        ),
        fc.constantFrom(null, undefined, [3], { x: 1 }),
        (key, junk) => {
          expect(decode(overviewOut, { ...base, [key]: junk }).ok).toBe(false);
        },
      ),
    );
  });

  it("maps light_unavailable to its message", () => {
    expect(messageKeyFor("light/cards", 503, "light_unavailable")).toBe(
      "Light.errors.unavailable",
    );
    expect(messageKeyFor("light/cards", 422, "invalid_request")).toBe(
      "Errors.client_defect",
    );
  });
});

describe("rankText", () => {
  it("shows a range exactly when the rank is tied", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 500 }),
        fc.integer({ min: 0, max: 20 }),
        (best, extra) => {
          const r = rankText({
            best,
            worst: best + extra,
            population: best + extra + 3,
          });
          expect(r.key).toBe(
            extra === 0 ? "Light.card.rank" : "Light.card.rankTied",
          );
          expect(r.values.best).toBeLessThanOrEqual(r.values.worst);
        },
      ),
    );
  });
});

const text = fc.string({ maxLength: 12 });
const row: fc.Arbitrary<ExportRow> = fc.record({
  goal: text,
  ingredient: text,
  ingredient_name_en: text,
  rank_best: fc.nat(),
  rank_worst: fc.nat(),
  population: fc.nat(),
  signal_types: fc.array(fc.stringMatching(/^[a-z_]{1,8}$/), { maxLength: 3 }),
  label_regions: fc.array(fc.constantFrom("US", "EU", "UK", "JP"), {
    maxLength: 4,
  }),
  labels_with_effect: fc.option(fc.nat(), { nil: null }),
  labels_total: fc.option(fc.nat(), { nil: null }),
  label_terms: fc.array(fc.stringMatching(/^[A-Za-z ,"]{1,10}$/), {
    maxLength: 3,
  }),
  faers_reports: fc.option(fc.nat(), { nil: null }),
  faers_ror: fc.option(fc.double({ noNaN: true, min: 0, max: 100 }), {
    nil: null,
  }),
  faers_ror_low: fc.option(fc.double({ noNaN: true, min: 0, max: 100 }), {
    nil: null,
  }),
  faers_ror_high: fc.option(fc.double({ noNaN: true, min: 0, max: 100 }), {
    nil: null,
  }),
  patient_reported_released: fc.option(fc.nat(), { nil: null }),
  source_ids: fc.array(fc.stringMatching(/^[a-z:._0-9]{1,12}$/), {
    maxLength: 3,
  }),
});

describe("toCsv", () => {
  it("round-trips every cell (lists joined with |)", () => {
    fc.assert(
      fc.property(fc.array(row, { maxLength: 8 }), (rows) => {
        const parsed = parseCsv(toCsv(rows));
        expect(parsed[0]).toEqual([...CSV_COLUMNS]);
        expect(parsed).toHaveLength(rows.length + 1);
        rows.forEach((r, i) => {
          CSV_COLUMNS.forEach((c, j) => {
            const v = r[c];
            const want =
              v === null ? "" : Array.isArray(v) ? v.join("|") : String(v);
            expect(parsed[i + 1]![j]).toBe(want);
          });
        });
      }),
    );
  });

  it("names files safely", () => {
    expect(fileName("ab/../c d", "csv")).toBe("janus-light-abcd-cc-by-4.0.csv");
  });
});

describe("nameIn", () => {
  it("prefers the locale, then English, then any label, then the key", () => {
    expect(nameIn({ en: "a", tr: "b" }, "tr")).toBe("b");
    expect(nameIn({ en: "a" }, "de")).toBe("a");
    expect(nameIn({ fr: "c" }, "de")).toBe("c");
    expect(nameIn({}, "de", "Q1")).toBe("Q1");
  });
});

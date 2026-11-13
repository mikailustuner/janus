// Plan D3.2: each validation card's CSV holds the numbers the card shows (same generated file),
// is valid RFC 4180 with a fixed header, uses dot decimals whatever the locale, and the citation
// names the release of CITATION.cff.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";

import {
  citationText,
  CSV_COLUMNS,
  csvFileName,
  studyRows,
  toCsv,
} from "./export";
import { CARDS, VALIDATION } from "./validation";

/** A small RFC 4180 reader, enough to check the writer. */
function parse(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      row.push(cell);
      cell = "";
    } else if (ch === "\r" && text[i + 1] === "\n") {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
      i++;
    } else cell += ch;
  }
  return rows;
}

describe("validation CSV", () => {
  it.each(CARDS)("%s: header, one row per number, dot decimals", (card) => {
    const rows = parse(toCsv(studyRows(card)));
    expect(rows[0]).toEqual([...CSV_COLUMNS]);
    expect(rows.length).toBeGreaterThan(2);
    for (const r of rows.slice(1)) {
      expect(r).toHaveLength(CSV_COLUMNS.length);
      expect(r[0]).toBe(card);
      for (const v of r.slice(2, 9)) expect(v).toMatch(/^(-?\d+(\.\d+)?)?$/);
    }
  });

  it("carries the headline numbers the cards show", () => {
    const cascade = parse(toCsv(studyRows("cascade")));
    const spec = cascade.find((r) => r[1] === "specificity_pairs")!;
    expect(Number(spec[2])).toBe(VALIDATION.cascade.specificity.k);
    expect(Number(spec[3])).toBe(VALIDATION.cascade.specificity.n);
    expect(Number(spec[5])).toBe(VALIDATION.cascade.specificity.low);
    const faers = parse(toCsv(studyRows("faers")));
    expect(Number(faers.find((r) => r[1] === "auc_ln_ror")![4])).toBe(
      VALIDATION.faers.auc.estimate,
    );
  });

  it("quotes any cell with a comma, quote or line break (property)", () => {
    check(
      fc.property(fc.string(), (s) => {
        const back = parse(toCsv([{ study: "cascade", measure: s }]));
        expect(back[1]![1]).toBe(s);
      }),
    );
  });

  it("names the file and the citation after the release in CITATION.cff", () => {
    const cff = readFileSync(
      join(import.meta.dirname, "../../../../CITATION.cff"),
      "utf8",
    );
    const version = /^version:\s*"([^"]+)"/m.exec(cff)![1]!;
    expect(csvFileName("faers")).toBe(`janus-faers-v${version}.csv`);
    expect(citationText()).toContain(`Version ${version}`);
    expect(citationText()).toContain("Üstüner M.");
  });
});

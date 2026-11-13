// The recorded API answers (`src/**/*.recorded.json`) are the demo-mode data of the site and are
// re-recorded with every pipeline release. This is the only test that reads them: each file decodes
// with the production decoder and holds the minimum the demo needs. Behaviour tests use the
// synthetic fixtures in `src/test/fixtures` and never assert on recorded content.
import { describe, expect, it } from "vitest";

import { decode } from "@/api/decode";
import {
  drugOut,
  drugsOut,
  evidenceOut,
  reasonKey,
  systemOut,
  type ModelKitFixture,
} from "@/modelkit/model";
import { reasonCodesOf, type ModelKitSet } from "@/test/fixtures/modelkit";

import { dataQualityReport } from "@/research/dataQuality";
import { onsetTable } from "@/research/onset";

import dataQuality from "@/research/data-quality.recorded.json";
import faersOnset from "@/research/faers-onset.recorded.json";
import modelkit from "@/modelkit/modelkit.recorded.json";
import modelkitM0 from "@/modelkit/modelkit.m0.recorded.json";

describe.each([
  ["modelkit.recorded.json", modelkit],
  ["modelkit.m0.recorded.json", modelkitM0],
])("%s", (_name, file) => {
  const fx = file as unknown as ModelKitFixture;
  const drugs = decode(drugsOut, fx.drugs);
  const drugKeys = Object.keys(fx.drug);
  const val = <T>(r: { ok: boolean; value?: T }): T => {
    if (!r.ok) throw new Error("does not decode");
    return r.value as T;
  };

  it("decodes with the production decoders", () => {
    expect(drugs.ok).toBe(true);
    expect(decode(systemOut, fx.validation).ok).toBe(true);
    for (const k of drugKeys)
      expect(decode(drugOut, fx.drug[k]).ok, `drug ${k}`).toBe(true);
    for (const k of Object.keys(fx.evidence))
      expect(decode(evidenceOut, fx.evidence[k]).ok, `evidence ${k}`).toBe(
        true,
      );
  });

  it("holds the minimum the demo needs: a drug list, a drug with a parameter set", () => {
    expect(val(drugs).drugs.length).toBeGreaterThanOrEqual(1);
    const withSet = drugKeys.filter(
      (k) => val(decode(drugOut, fx.drug[k])).parameter_set !== null,
    );
    expect(withSet.length).toBeGreaterThanOrEqual(1);
  });

  it("uses only reason codes the interface has a message for", () => {
    const set = {
      drug: Object.fromEntries(
        drugKeys.map((k) => [k, val(decode(drugOut, fx.drug[k]))]),
      ),
      evidence: Object.fromEntries(
        Object.keys(fx.evidence).map((k) => [
          k,
          val(decode(evidenceOut, fx.evidence[k])),
        ]),
      ),
      validation: val(decode(systemOut, fx.validation)),
    } as unknown as ModelKitSet;
    expect([...reasonCodesOf(set)].filter((c) => !reasonKey(c))).toEqual([]);
  });
});

describe("data-quality.recorded.json", () => {
  const r = decode(dataQualityReport, dataQuality.report);

  it("decodes and holds at least one finding with a CSV and a Markdown file", () => {
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.findings.length).toBeGreaterThanOrEqual(1);
    expect(dataQuality.csv.length).toBeGreaterThan(0);
    expect(dataQuality.md.length).toBeGreaterThan(0);
  });

  it("carries no TİTCK barcode or GTIN (the page can show the whole file)", () => {
    expect(JSON.stringify(dataQuality)).not.toMatch(/(?<!\d)0?869\d{10}(?!\d)/);
  });
});

describe("faers-onset.recorded.json", () => {
  const r = decode(onsetTable, faersOnset.table);

  it("decodes and holds the 65 PIPC positions with a CSV file", () => {
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.rows.map((x) => x.pipc_position)).toEqual(
      Array.from({ length: 65 }, (_, i) => i + 1),
    );
    expect(faersOnset.csv.length).toBeGreaterThan(0);
  });
});

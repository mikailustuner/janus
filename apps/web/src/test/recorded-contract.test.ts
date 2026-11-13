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

import {
  defaultRequest,
  job,
  serverCompounds,
  type SimulationFixture,
} from "@/simulation/client";
import { catalogueOut, PRESENT_CODES, seanceOut } from "@/seance/model";
import type { SeanceFixture } from "@/seance/client";
import { cardsOut, exportOut, overviewOut, validationOut } from "@/light/model";
import { openOutcomes } from "@/open/model";
import { dataQualityReport } from "@/research/dataQuality";
import { onsetTable } from "@/research/onset";

import simulate from "@/simulation/simulate.recorded.json";
import light from "@/light/fixture.recorded.json";
import seance from "@/seance/fixture.recorded.json";
import openData from "@/open/fixture.recorded.json";
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

describe("simulate.recorded.json", () => {
  const fx = simulate as unknown as SimulationFixture;
  const compounds = decode(serverCompounds, fx.compounds);

  it("decodes: the compounds list and every recorded job", () => {
    expect(compounds.ok).toBe(true);
    expect(fx.jobs.length).toBeGreaterThanOrEqual(1);
    for (const j of fx.jobs) expect(decode(job, j.job).ok).toBe(true);
  });

  it("holds a done job for the form's default request of each model (the demo offers those)", () => {
    if (!compounds.ok) throw new Error("compounds do not decode");
    for (const kind of ["compartmental", "httk_population"] as const) {
      const want = defaultRequest(compounds.value, kind);
      const hit = fx.jobs.find(
        (j) =>
          JSON.stringify(Object.entries(j.request).sort()) ===
          JSON.stringify(Object.entries(want).sort()),
      );
      expect(hit, kind).toBeTruthy();
      const d = decode(job, hit!.job);
      expect(d.ok && d.value.state === "done" && d.value.result !== null).toBe(
        true,
      );
    }
  });
});

describe("open/fixture.recorded.json", () => {
  const r = decode(openOutcomes, openData.outcomes);

  it("decodes, keeps the release rule (k >= 20, hidden cells never listed) and has a CSV header", () => {
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.release_rule.k).toBeGreaterThanOrEqual(20);
    expect(r.value.release_rule.hidden_cells_listed).toBe(false);
    expect(openData.csv.split("\n")[0]).toMatch(/^dataset_version,/);
  });
});

describe("seance/fixture.recorded.json", () => {
  const fx = seance as unknown as SeanceFixture;

  it("decodes: the catalogue and every recorded pair, each pair listed in the catalogue", () => {
    const cat = decode(catalogueOut, fx.catalogue);
    expect(cat.ok).toBe(true);
    expect(fx.pairs.length).toBeGreaterThanOrEqual(1);
    for (const p of fx.pairs) {
      const a = decode(seanceOut, p.answer);
      expect(a.ok).toBe(true);
      if (cat.ok)
        expect(
          cat.value.pairs.some(
            (x) =>
              x.substance === p.request.substance &&
              x.condition === p.request.condition,
          ),
        ).toBe(true);
    }
  });

  it("uses only present-witness caveat codes the screen can word", () => {
    for (const p of fx.pairs) {
      const a = decode(seanceOut, p.answer);
      if (a.ok)
        for (const c of a.value.witnesses.present.codes)
          expect(PRESENT_CODES as readonly string[]).toContain(c);
    }
  });
});

describe("light/fixture.recorded.json", () => {
  it("decodes: overview, every goal's cards, validation and export", () => {
    expect(decode(overviewOut, light.overview).ok).toBe(true);
    expect(Object.keys(light.cards).length).toBeGreaterThanOrEqual(1);
    for (const [goal, v] of Object.entries(light.cards))
      expect(decode(cardsOut, v).ok, goal).toBe(true);
    expect(decode(validationOut, light.validation).ok).toBe(true);
    expect(decode(exportOut, light.export).ok).toBe(true);
  });

  it("holds at least one hypothesis card and one export row", () => {
    const cards = Object.values(light.cards).flatMap(
      (v) => (v as { cards: unknown[] }).cards,
    );
    expect(cards.length).toBeGreaterThanOrEqual(1);
    expect(
      (light.export as { rows: unknown[] }).rows.length,
    ).toBeGreaterThanOrEqual(1);
  });
});

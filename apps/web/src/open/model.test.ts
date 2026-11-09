// Feature: open-data Req 3 (design §4): the recorded file decodes, the dashboard partition
// keeps every cell once, the demo downloads are the recorded files.
import { describe, expect, it } from "vitest";

import * as D from "@/api/decode";
import { check, fc } from "@/test/fc";

import fixture from "./fixture.recorded.json";
import {
  byLayer,
  demoOpenData,
  openOutcomes,
  type OpenOutcomes,
} from "./model";

const fx = fixture as unknown as {
  recorded: string;
  outcomes: unknown;
  csv: string;
};

const cellArb = fc.record({
  layer: fc.constantFrom("contributions" as const, "outcomes" as const),
  ingredients: fc.constantFrom<string[]>(["Q1"], ["Q1", "Q2"]),
  event: fc.constantFrom("cough", "peripheral_oedema"),
  direction: fc.constantFrom("adverse" as const, "benefit" as const),
  region: fc.constantFrom("TR" as const, "EU" as const, "US" as const),
  value: fc.nat(500),
});

describe("open outcome dataset", () => {
  it("the recorded answer decodes and is the honest empty state", () => {
    const r = D.decode(openOutcomes, fx.outcomes);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.cells).toEqual([]);
    expect(r.value.release_rule.k).toBeGreaterThanOrEqual(20);
    expect(r.value.release_rule.hidden_cells_listed).toBe(false);
    expect(fx.csv.trim()).toBe(
      "dataset_version,snapshot_date,layer,ingredients,event,direction,region,value",
    );
  });

  it("byLayer keeps every cell exactly once, in its layer, in order", () => {
    const base = D.decode(openOutcomes, fx.outcomes);
    if (!base.ok) throw new Error(base.path);
    check(
      fc.property(fc.array(cellArb, { maxLength: 20 }), (cells) => {
        const o: OpenOutcomes = { ...base.value, cells };
        const parts = byLayer(o);
        expect(parts.flatMap((p) => p.cells).length).toBe(cells.length);
        for (const p of parts)
          expect(p.cells).toEqual(cells.filter((c) => c.layer === p.layer));
      }),
    );
  });

  it("demo downloads are the recorded files as data URLs (no request)", () => {
    const c = demoOpenData(fx);
    const csv = c.download("csv");
    expect(csv.startsWith("data:text/csv")).toBe(true);
    expect(decodeURIComponent(csv.split(",").slice(1).join(","))).toBe(fx.csv);
    const json = c.download("json");
    expect(
      JSON.parse(decodeURIComponent(json.split(",").slice(1).join(","))),
    ).toEqual(fx.outcomes);
  });
});

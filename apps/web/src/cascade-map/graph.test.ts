// Feature: cascade-map, Properties P1, P4, P5: the committed graph equals the generator output; every
// PIPC rule is exactly one edge; the layout is deterministic, inside the canvas, without overlap.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";

import { CANVAS, generate, layout } from "../../scripts/gen-cascade-map.mjs";
import { parseCsv, serialise } from "../../scripts/gen-vocabulary.mjs";

import { graph } from "./model";

const repoRoot = join(import.meta.dirname, "../../../..");
const pipc = parseCsv(readFileSync(join(repoRoot, "data/pipc.csv"), "utf8"));
const rules = parseCsv(
  readFileSync(join(repoRoot, "data/pipc_rules.csv"), "utf8"),
);

describe("generated graph (P1)", () => {
  it("equals the generator output (run `node scripts/gen-cascade-map.mjs` after a data change)", () => {
    const files = generate(repoRoot) as Record<string, unknown>;
    expect(readFileSync(join(import.meta.dirname, "graph.json"), "utf8")).toBe(
      serialise(files["graph.json"]),
    );
  });

  it("has exactly one edge per PIPC rule row, from its index class to its marker class", () => {
    expect(graph.edges.map((e) => e.row).sort((a, b) => a - b)).toEqual(
      pipc.map((p) => Number(p.position)),
    );
    expect(graph.edges).toHaveLength(65);
    const ids = new Set(graph.nodes.map((n) => n.id));
    for (const e of graph.edges) {
      const r = rules.find((x) => Number(x.position) === e.row)!;
      expect(ids.has(e.from) && ids.has(e.to)).toBe(true);
      expect(r.index_class!.startsWith(e.from)).toBe(true);
      if (r.marker_class) expect(r.marker_class.startsWith(e.to)).toBe(true);
      else expect(e.to).toBe(`row${e.row}:marker`);
      expect(!!e.unmatchable).toBe(!!r.unmatchable_role);
    }
  });

  it("lists each node's rows exactly as its edges (no node without an edge)", () => {
    for (const n of graph.nodes) {
      expect(n.index).toEqual(
        graph.edges.filter((e) => e.from === n.id).map((e) => e.row),
      );
      expect(n.marker).toEqual(
        graph.edges.filter((e) => e.to === n.id).map((e) => e.row),
      );
      expect(n.index.length + n.marker.length).toBeGreaterThan(0);
    }
  });
});

type Pos = Map<string, [number, number]>;

function assertInside(pos: Pos) {
  for (const [x, y] of pos.values()) {
    expect(x).toBeGreaterThanOrEqual(CANVAS.margin);
    expect(x).toBeLessThanOrEqual(CANVAS.width - CANVAS.margin);
    expect(y).toBeGreaterThanOrEqual(CANVAS.margin);
    expect(y).toBeLessThanOrEqual(CANVAS.height - CANVAS.margin);
  }
}

function minDistance(pos: Pos) {
  const p = [...pos.values()];
  let min = Infinity;
  for (let i = 0; i < p.length; i++)
    for (let j = i + 1; j < p.length; j++)
      min = Math.min(min, Math.hypot(p[i]![0] - p[j]![0], p[i]![1] - p[j]![1]));
  return min;
}

describe("layout (P4, P5)", () => {
  it("the committed layout is inside the canvas and keeps the minimum distance", () => {
    const pos: Pos = new Map(graph.nodes.map((n) => [n.id, [n.x, n.y]]));
    assertInside(pos);
    expect(minDistance(pos)).toBeGreaterThanOrEqual(CANVAS.minDistance);
  });

  // Random graphs of the rule base's size: same input → same output; inside; no overlap.
  const graphArb = fc.integer({ min: 2, max: 70 }).chain((n) =>
    fc.record({
      n: fc.constant(n),
      links: fc.array(fc.tuple(fc.nat(n - 1), fc.nat(n - 1)), {
        maxLength: 80,
      }),
    }),
  );

  it("is deterministic, inside the canvas and without overlap for any graph", () => {
    check(
      fc.property(graphArb, ({ n, links }) => {
        const ids = Array.from(
          { length: n },
          (_, i) => `c${String(i).padStart(2, "0")}`,
        );
        const l = links.map(([a, b]) => [ids[a]!, ids[b]!] as [string, string]);
        const a = layout(ids, l) as Pos;
        const b = layout(ids, l) as Pos;
        expect([...a.entries()]).toEqual([...b.entries()]);
        assertInside(a);
        expect(minDistance(a)).toBeGreaterThanOrEqual(CANVAS.minDistance);
      }),
      { numRuns: 25 },
    );
  });
});

// Feature: cascade-map, Properties P2, P3, P6, P7, P8: filters only remove; matched edges ⊆ edges
// and come from the returned findings only; cannot-be-checked follows the result; keyboard
// navigation reaches every visible star; names come from the vocabulary.
import { describe, expect, it } from "vitest";

import type { CascadeResult, Finding } from "@/api/contracts";
import { check, fc } from "@/test/fc";
import { RESULTS, VOCAB_EN, cascadeResultArb } from "@/test/results";
import tr from "@/vocabulary/tr.json";
import type { Loaded, Vocabulary } from "@/vocabulary";

import {
  byLabel,
  cannotCheck,
  edgeGeometry,
  filterEdges,
  fold,
  graph,
  labels,
  matchedEdges,
  matchedRows,
  move,
  NO_FILTER,
  nodeById,
  touchedNodes,
  type Direction,
  type Filter,
} from "./model";

const names = labels(graph, VOCAB_EN);
const nodes = nodeById(graph);
const VOCAB_TR: Loaded = {
  ...VOCAB_EN,
  locale: "tr",
  vocab: tr as unknown as Vocabulary,
};

const filterArb: fc.Arbitrary<Filter> = fc.record({
  classId: fc.option(fc.constantFrom(...graph.nodes.map((n) => n.id)), {
    nil: null,
  }),
  event: fc.option(
    fc.constantFrom(...new Set(graph.edges.map((e) => e.event))),
    { nil: null },
  ),
  query: fc.oneof(
    fc.constant(""),
    fc.constantFrom(
      "statin",
      "nausea",
      "Antiemetic",
      "  laxative ",
      "ÖKSÜRÜK",
      "zz",
      "12",
    ),
    fc.string({ maxLength: 4 }),
  ),
});

describe("names (Req 1.3)", () => {
  it("label every node with the shortest published name of its rows", () => {
    expect(names.get("statin")).toBe("HMG Co-A reductase inhibitor");
    expect(names.get("nsaid")).toBe("NSAID");
    expect(names.get("beta_blocker")).toBe("Beta-blocker");
    expect(names.get("row27:marker")).toBe("Bismuth subsalicylate");
    for (const n of graph.nodes) expect(names.get(n.id)).not.toBe(n.id);
  });
  it("use the vocabulary of the interface language", () => {
    expect(labels(graph, VOCAB_TR).get("statin")).toBe(
      "HMG-KoA redüktaz inhibitörü",
    );
  });
});

describe("filters (P2, Req 3)", () => {
  it("no filter shows every edge once", () => {
    expect(filterEdges(graph, NO_FILTER, VOCAB_EN, names)).toEqual(graph.edges);
  });
  it("only remove: the result is a subsequence of the edges, and adding a filter never adds", () => {
    check(
      fc.property(filterArb, filterArb, (f, g) => {
        const shown = filterEdges(graph, f, VOCAB_EN, names);
        const idx = shown.map((e) => graph.edges.indexOf(e));
        expect(idx.every((i) => i >= 0)).toBe(true);
        expect([...idx].sort((a, b) => a - b)).toEqual(idx);
        // Narrowing: f plus g's class filter is a subset of f.
        const narrower = filterEdges(
          graph,
          { ...f, classId: f.classId ?? g.classId },
          VOCAB_EN,
          names,
        );
        expect(narrower.every((e) => shown.includes(e))).toBe(true);
        for (const e of shown) {
          if (f.classId) expect([e.from, e.to]).toContain(f.classId);
          if (f.event) expect(e.event).toBe(f.event);
        }
        // Nodes shown are exactly those touched by a shown edge.
        const touched = touchedNodes(shown);
        for (const id of touched)
          expect(shown.some((e) => e.from === id || e.to === id)).toBe(true);
      }),
    );
  });
  it("search ignores case and diacritics", () => {
    expect(fold("ÖKSÜRÜK İlaç", "tr")).toBe("oksuruk ilac");
    const rows = (q: string, v: Loaded) =>
      filterEdges(graph, { ...NO_FILTER, query: q }, v, labels(graph, v)).map(
        (e) => e.row,
      );
    expect(rows("oksuruk", VOCAB_TR)).toContain(1);
    expect(rows("COUGH", VOCAB_EN)).toContain(1);
    expect(rows("statin myalgia", VOCAB_EN)).toEqual([9, 10, 11]);
  });
});

const anyFinding = (rule: string): Finding => ({
  ...RESULTS[0]!.findings[0]!,
  rule_id: rule,
});

describe("matches (P3, Req 5)", () => {
  it("matched edges are a subset of the edges and exactly the rows of the returned findings", () => {
    check(
      fc.property(
        cascadeResultArb,
        fc.array(fc.integer({ min: 1, max: 120 }), { maxLength: 6 }),
        ({ result: base }, extra) => {
          const r: CascadeResult = {
            ...base,
            findings: [
              ...base.findings,
              ...extra.map((n) => anyFinding(`pipc:${n}`)),
            ],
          };
          const m = matchedEdges(graph, r);
          expect(m.every((e) => graph.edges.includes(e))).toBe(true);
          const rows = new Set(
            r.findings.map((f) => Number(f.rule_id.slice(5))),
          );
          expect(m.map((e) => e.row).sort((a, b) => a - b)).toEqual(
            graph.edges
              .map((e) => e.row)
              .filter((row) => rows.has(row))
              .sort((a, b) => a - b),
          );
          // Positions point back at findings with that rule id.
          for (const [row, ps] of matchedRows(r))
            for (const p of ps)
              expect(r.findings[p]!.rule_id).toBe(`pipc:${row}`);
        },
      ),
    );
  });
  it("no result, no matches", () => {
    expect(matchedEdges(graph, null)).toEqual([]);
  });
  it("the Istanbul demo matches rows 5, 6, 9, 12", () => {
    expect(matchedEdges(graph, RESULTS[0]!).map((e) => e.row)).toEqual([
      5, 6, 9, 12,
    ]);
  });
});

describe("cannot be checked (Req 4.2)", () => {
  it("follows the result's lists, else the rule base's unmatchable rows", () => {
    expect([...cannotCheck(graph, null).keys()]).toEqual([27, 57]);
    const r: CascadeResult = {
      ...RESULTS[0]!,
      rules: {
        ...RESULTS[0]!.rules,
        disabled: [
          { rule_id: "pipc:3", reason: "all_sources_retracted", removed: [] },
        ],
        not_matchable: [
          { rule_id: "pipc:27", role: "marker", reason: "no_atc_code" },
        ],
      },
    };
    const c = cannotCheck(graph, r);
    expect(c.get(3)).toEqual({
      kind: "disabled",
      reason: "all_sources_retracted",
    });
    expect(c.get(27)).toEqual({ kind: "not_matchable", reason: "no_atc_code" });
    expect(c.has(57)).toBe(false);
  });
});

describe("keyboard (P6, Req 6.2)", () => {
  const DIRS: Direction[] = ["left", "right", "up", "down"];
  const reach = (visible: Set<string>, start: string) => {
    const seen = new Set([start]);
    const todo = [start];
    while (todo.length) {
      const c = todo.pop()!;
      for (const d of DIRS) {
        const n = move(nodes, visible, c, d);
        if (!seen.has(n)) {
          seen.add(n);
          todo.push(n);
        }
      }
    }
    return seen;
  };

  it("arrow keys reach every visible star from any visible star, for any filter", () => {
    check(
      fc.property(filterArb, (f) => {
        const shown = filterEdges(graph, f, VOCAB_EN, names);
        const visible = touchedNodes(shown);
        for (const start of visible)
          expect(reach(visible, start).size).toBe(visible.size);
      }),
      { numRuns: 60 },
    );
  });

  it("a move stays on a visible star and goes in the pressed direction", () => {
    check(
      fc.property(filterArb, fc.constantFrom(...DIRS), (f, d) => {
        const shown = filterEdges(graph, f, VOCAB_EN, names);
        const visible = touchedNodes(shown);
        for (const id of visible) {
          const n = move(nodes, visible, id, d);
          expect(visible.has(n)).toBe(true);
          if (n === id) continue;
          const a = nodes.get(id)!;
          const b = nodes.get(n)!;
          const along = {
            left: a.x - b.x,
            right: b.x - a.x,
            up: a.y - b.y,
            down: b.y - a.y,
          }[d];
          expect(along).toBeGreaterThan(0);
        }
      }),
      { numRuns: 40 },
    );
  });

  it("arrow keys reach every star under every single class or event filter", () => {
    const filters: Filter[] = [
      ...graph.nodes.map((n) => ({ ...NO_FILTER, classId: n.id })),
      ...[...new Set(graph.edges.map((e) => e.event))].map((event) => ({
        ...NO_FILTER,
        event,
      })),
      NO_FILTER,
    ];
    for (const f of filters) {
      const visible = touchedNodes(filterEdges(graph, f, VOCAB_EN, names));
      for (const start of visible)
        expect(reach(visible, start).size).toBe(visible.size);
    }
  });

  it("orders stars by label for Home and End", () => {
    const order = byLabel(names.keys(), names, "en");
    expect(order).toHaveLength(65);
    expect(names.get(order[0]!)! <= names.get(order[1]!)!).toBe(true);
  });
});

describe("drawing", () => {
  it("draws every edge between its two stars", () => {
    for (const e of graph.edges) {
      const a = nodes.get(e.from)!;
      const b = nodes.get(e.to)!;
      const g = edgeGeometry(a, b);
      expect(g.d.startsWith(`M${a.x} ${a.y}Q`)).toBe(true);
      expect(g.d.endsWith(` ${b.x} ${b.y}`)).toBe(true);
      expect(Number.isFinite(g.angle)).toBe(true);
    }
  });
});

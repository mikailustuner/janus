/**
 * The cascade map's view model (cascade-map design §5). Pure: it takes the generated graph, the
 * vocabulary of the interface language and, when there is one, the `CascadeResult` the API or the
 * demo fixture returned. It decides nothing medical (experience DP3): matches are the rule ids of
 * the returned findings, "cannot be checked" is the result's own rule lists.
 */
import type { CascadeResult } from "@/api/contracts";
import { ruleRow, type Loaded } from "@/vocabulary";

import graphJson from "./graph.json";

export interface GraphNode {
  id: string;
  x: number;
  y: number;
  /** Rows where this class is the first medicine (index). */
  index: number[];
  /** Rows where this class is the second medicine (marker). */
  marker: number[];
}

export interface GraphEdge {
  row: number;
  from: string;
  to: string;
  event: string;
  supporting: string[];
  unmatchable: { role: string; reason: string } | null;
}

export interface Graph {
  sources: Record<string, string>;
  canvas: {
    width: number;
    height: number;
    margin: number;
    minDistance: number;
  };
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export const graph = graphJson as Graph;

export const nodeById = (g: Graph) => new Map(g.nodes.map((n) => [n.id, n]));

// --- names (Req 1.3) -----------------------------------------------------------------------------

/** The shortest published name of a class in the interface language (ties: index rows first). */
export function nodeLabel(node: GraphNode, v: Loaded): string {
  const names = nodeNames(node, v);
  // Stable sort: equal lengths keep the order index rows, then marker rows (ascending).
  return [...names].sort((a, b) => a.length - b.length)[0] ?? node.id;
}

export function eventLabel(key: string, v: Loaded): string {
  return v.vocab.events[key]?.label ?? key;
}

/** Every published name of a class in the interface language (the search looks at all of them). */
export function nodeNames(node: GraphNode, v: Loaded): string[] {
  return [
    ...node.index.map((row) => v.vocab.cascades[String(row)]?.drug_a),
    ...node.marker.map((row) => v.vocab.cascades[String(row)]?.drug_b),
  ].filter((t): t is string => !!t);
}

export function labels(g: Graph, v: Loaded): Map<string, string> {
  return new Map(g.nodes.map((n) => [n.id, nodeLabel(n, v)]));
}

// --- filters (Req 3) -----------------------------------------------------------------------------

export interface Filter {
  classId: string | null;
  event: string | null;
  query: string;
}

export const NO_FILTER: Filter = { classId: null, event: null, query: "" };

/** Lower case without diacritics, for a forgiving search in five languages. */
export function fold(s: string, locale: string): string {
  return s
    .toLocaleLowerCase(locale)
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/ı/g, "i");
}

/** The edges that satisfy every active filter, in graph order. Only removes (P2). */
export function filterEdges(
  g: Graph,
  f: Filter,
  v: Loaded,
  names: Map<string, string>,
): GraphEdge[] {
  const q = fold(f.query.trim(), v.locale);
  const byId = nodeById(g);
  const all = (id: string) => [names.get(id), ...nodeNames(byId.get(id)!, v)];
  return g.edges.filter((e) => {
    if (f.classId && e.from !== f.classId && e.to !== f.classId) return false;
    if (f.event && e.event !== f.event) return false;
    if (!q) return true;
    const c = v.vocab.cascades[String(e.row)];
    const hay = [
      ...all(e.from),
      ...all(e.to),
      c?.drug_a,
      c?.drug_b,
      c?.adverse_event,
      eventLabel(e.event, v),
      String(e.row),
    ]
      .filter(Boolean)
      .map((s) => fold(s!, v.locale));
    return q.split(/\s+/).every((word) => hay.some((h) => h.includes(word)));
  });
}

/** The nodes touched by the given edges. */
export function touchedNodes(edges: readonly GraphEdge[]): Set<string> {
  return new Set(edges.flatMap((e) => [e.from, e.to]));
}

// --- the person's findings (Req 5, experience DP3) -----------------------------------------------

/** Rule row → positions of the returned findings with that rule id (API order). */
export function matchedRows(
  result: CascadeResult | null,
): Map<number, number[]> {
  const out = new Map<number, number[]>();
  result?.findings.forEach((f, position) => {
    const row = ruleRow(f.rule_id);
    if (row === null) return;
    out.set(row, [...(out.get(row) ?? []), position]);
  });
  return out;
}

/** The edges of the returned findings (a subset of the graph's edges, P3). */
export function matchedEdges(
  g: Graph,
  result: CascadeResult | null,
): GraphEdge[] {
  const rows = matchedRows(result);
  return g.edges.filter((e) => rows.has(e.row));
}

export type CannotCheck = {
  kind: "not_matchable" | "disabled";
  reason: string;
};

/**
 * Rules that cannot be checked: the result's own lists when there is a result (the API decides,
 * integrity included), else the rule base's static `unmatchable` rows.
 */
export function cannotCheck(
  g: Graph,
  result: CascadeResult | null,
): Map<number, CannotCheck> {
  const out = new Map<number, CannotCheck>();
  if (result) {
    for (const n of result.rules.not_matchable) {
      const row = ruleRow(n.rule_id);
      if (row !== null)
        out.set(row, { kind: "not_matchable", reason: n.reason });
    }
    for (const d of result.rules.disabled) {
      const row = ruleRow(d.rule_id);
      if (row !== null) out.set(row, { kind: "disabled", reason: d.reason });
    }
    return out;
  }
  for (const e of g.edges)
    if (e.unmatchable)
      out.set(e.row, { kind: "not_matchable", reason: e.unmatchable.reason });
  return out;
}

// --- keyboard (Req 6.2) --------------------------------------------------------------------------

export type Direction = "left" | "right" | "up" | "down";
const VEC: Record<Direction, [number, number]> = {
  left: [-1, 0],
  right: [1, 0],
  up: [0, -1],
  down: [0, 1],
};

/**
 * The star an arrow key moves to: the closest visible star in that half-plane, scored
 * along + 2 × sideways (ties by id), else stay. No graph-neighbour preference: it left some stars
 * unreachable by arrows (DP7); the panel lists a star's patterns instead.
 */
export function move(
  nodes: Map<string, GraphNode>,
  visible: ReadonlySet<string>,
  current: string,
  dir: Direction,
): string {
  const c = nodes.get(current);
  if (!c) return current;
  const [dx, dy] = VEC[dir];
  let best: { id: string; score: number } | null = null;
  for (const id of visible) {
    if (id === current) continue;
    const n = nodes.get(id)!;
    const along = (n.x - c.x) * dx + (n.y - c.y) * dy;
    if (along <= 0) continue;
    const score = along + 2 * Math.abs((n.x - c.x) * dy - (n.y - c.y) * dx);
    if (!best || score < best.score || (score === best.score && id < best.id))
      best = { id, score };
  }
  return best?.id ?? current;
}

/** Visible stars in label order (Home / End, the class select and the list). */
export function byLabel(
  ids: Iterable<string>,
  names: Map<string, string>,
  locale: string,
): string[] {
  const coll = new Intl.Collator(locale);
  return [...ids].sort(
    (a, b) =>
      coll.compare(names.get(a) ?? a, names.get(b) ?? b) || (a < b ? -1 : 1),
  );
}

// --- drawing ---------------------------------------------------------------------------------------

/**
 * A gently curved line from `a` to `b` (control point 12 % of the length to the right of the
 * direction), with the end tangent's angle for the arrowhead, in layout units.
 */
export function edgeGeometry(a: GraphNode, b: GraphNode) {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const cx = mx - dy * 0.12;
  const cy = my + dx * 0.12;
  const angle = (Math.atan2(b.y - cy, b.x - cx) * 180) / Math.PI;
  return {
    d: `M${a.x} ${a.y}Q${cx.toFixed(1)} ${cy.toFixed(1)} ${b.x} ${b.y}`,
    angle: Math.round(angle * 10) / 10,
    /** The curve's midpoint (t = 0.5), where the selected line shows its side effect. */
    mid: [(a.x + 2 * cx + b.x) / 4, (a.y + 2 * cy + b.y) / 4] as const,
  };
}

/** A fixed star field for Night Pharmacy (decorative, aria-hidden), from a small LCG. */
export function starField(count: number, w: number, h: number, seed = 7) {
  let s = seed;
  const next = () => {
    s = (s * 1103515245 + 12345) % 2147483648;
    return s / 2147483648;
  };
  return Array.from({ length: count }, () => ({
    x: Math.round(next() * w),
    y: Math.round(next() * h),
    r: Math.round((0.6 + next() * 1.6) * 10) / 10,
    o: Math.round((0.25 + next() * 0.5) * 100) / 100,
  }));
}

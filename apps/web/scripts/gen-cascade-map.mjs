/**
 * Generates the cascade map graph (cascade-map design §3, §4, DP2, DP3): one node per class of the
 * PIPC rule base, one directed edge per rule row, and a deterministic force layout computed here,
 * once, so the client never runs a simulation. Inputs: data/pipc.csv, data/pipc_rules.csv and the
 * active rows of the Janus event vocabulary. Names are not stored: the client takes them from the
 * generated vocabulary of the interface language. A vitest parity test regenerates in memory and
 * compares with the committed file (P1).
 *
 *   node apps/web/scripts/gen-cascade-map.mjs          write src/cascade-map/graph.json
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { parseCsv, serialise } from "./gen-vocabulary.mjs";

/** Canvas in layout units (4:5, a phone's portrait map); see design §4 for the numbers. */
export const CANVAS = {
  width: 1000,
  height: 1250,
  margin: 70,
  minDistance: 80,
};

const sha256 = (text) => createHash("sha256").update(text).digest("hex");

/** Class id → node id: one star per class, whatever role suffix the rule base uses (DP3). */
export function nodeId(classId, row, role) {
  return classId
    ? classId.replace(/_(index_eye|index|marker)$/, "")
    : `row${row}:${role}`;
}

/**
 * Fruchterman–Reingold with a fixed start (golden-angle spiral over the sorted ids), a fixed number
 * of steps and linear cooling, then a scale to the canvas and a collision pass that enforces the
 * minimum distance. Pure arithmetic in a fixed order: the same input gives the same coordinates.
 */
export function layout(ids, links, canvas = CANVAS) {
  const n = ids.length;
  const { width: W, height: H, margin: M, minDistance: D } = canvas;
  const at = new Map(ids.map((id, i) => [id, i]));
  const pos = ids.map((_, i) => {
    const r = Math.sqrt(i + 0.5) / Math.sqrt(n);
    const a = i * 2.399963229728653;
    return [
      W / 2 + r * (W / 2 - M) * Math.cos(a),
      H / 2 + r * (H / 2 - M) * Math.sin(a),
    ];
  });
  const pairs = links.map(([a, b]) => [at.get(a), at.get(b)]);
  const k = 0.9 * Math.sqrt(((W - 2 * M) * (H - 2 * M)) / n);
  const steps = 700;
  for (let s = 0; s < steps; s++) {
    const temp = (W / 10) * (1 - s / steps) + 1;
    const disp = pos.map(() => [0, 0]);
    for (let i = 0; i < n; i++)
      for (let j = i + 1; j < n; j++) {
        let dx = pos[i][0] - pos[j][0];
        let dy = pos[i][1] - pos[j][1];
        let d = Math.hypot(dx, dy);
        if (d < 1e-6) {
          dx = 1e-3 * (j - i);
          dy = 1e-3;
          d = Math.hypot(dx, dy);
        }
        const f = (k * k) / d;
        disp[i][0] += (dx / d) * f;
        disp[i][1] += (dy / d) * f;
        disp[j][0] -= (dx / d) * f;
        disp[j][1] -= (dy / d) * f;
      }
    for (const [i, j] of pairs) {
      const dx = pos[i][0] - pos[j][0];
      const dy = pos[i][1] - pos[j][1];
      const d = Math.max(Math.hypot(dx, dy), 1e-6);
      const f = (d * d) / k;
      disp[i][0] -= (dx / d) * f;
      disp[i][1] -= (dy / d) * f;
      disp[j][0] += (dx / d) * f;
      disp[j][1] += (dy / d) * f;
    }
    for (let i = 0; i < n; i++) {
      // Gravity keeps the small components near the centre (the rule base is not connected).
      disp[i][0] += (W / 2 - pos[i][0]) * 0.06 * (k / 100);
      disp[i][1] += (H / 2 - pos[i][1]) * 0.06 * (k / 100);
      const d = Math.max(Math.hypot(disp[i][0], disp[i][1]), 1e-6);
      const step = Math.min(d, temp);
      pos[i][0] += (disp[i][0] / d) * step;
      pos[i][1] += (disp[i][1] / d) * step;
    }
  }
  // Scale the bounding box to the canvas inside the margin (aspect kept per axis: fills the card).
  const xs = pos.map((p) => p[0]);
  const ys = pos.map((p) => p[1]);
  const [x0, x1, y0, y1] = [
    Math.min(...xs),
    Math.max(...xs),
    Math.min(...ys),
    Math.max(...ys),
  ];
  for (const p of pos) {
    p[0] = M + ((p[0] - x0) / Math.max(x1 - x0, 1)) * (W - 2 * M);
    p[1] = M + ((p[1] - y0) / Math.max(y1 - y0, 1)) * (H - 2 * M);
  }
  // Collision pass: push pairs apart to D (+2 so rounding keeps the distance), clamp to the margin.
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  for (let round = 0; round < 400; round++) {
    let moved = false;
    for (let i = 0; i < n; i++)
      for (let j = i + 1; j < n; j++) {
        const dx = pos[j][0] - pos[i][0];
        const dy = pos[j][1] - pos[i][1];
        const d = Math.hypot(dx, dy);
        if (d >= D + 2) continue;
        moved = true;
        const ux = d > 1e-6 ? dx / d : 1;
        const uy = d > 1e-6 ? dy / d : 0;
        const push = (D + 2 - d) / 2 + 0.01;
        pos[i][0] -= ux * push;
        pos[i][1] -= uy * push;
        pos[j][0] += ux * push;
        pos[j][1] += uy * push;
      }
    for (const p of pos) {
      p[0] = clamp(p[0], M, W - M);
      p[1] = clamp(p[1], M, H - M);
    }
    if (!moved) break;
  }
  return new Map(
    ids.map((id, i) => [id, [Math.round(pos[i][0]), Math.round(pos[i][1])]]),
  );
}

/** Returns `{ "graph.json": object }` for src/cascade-map. */
export function generate(repoRoot) {
  const files = {
    pipc: "data/pipc.csv",
    rules: "data/pipc_rules.csv",
    events: "apps/api/janus/memory/memory_events.csv",
  };
  const text = Object.fromEntries(
    Object.entries(files).map(([k, p]) => [
      k,
      readFileSync(join(repoRoot, p), "utf8"),
    ]),
  );
  const pipc = parseCsv(text.pipc);
  const rules = new Map(parseCsv(text.rules).map((r) => [r.position, r]));
  const events = parseCsv(text.events).filter((r) => r.status === "active");
  const eventOf = (row) => {
    const keys = events
      .filter((e) =>
        e.pipc_positions.split(";").filter(Boolean).map(Number).includes(row),
      )
      .map((e) => e.key);
    if (keys.length !== 1)
      throw new Error(`row ${row}: ${keys.length} event keys`);
    return keys[0];
  };

  const edges = pipc.map((p) => {
    const row = Number(p.position);
    const r = rules.get(p.position);
    if (!r) throw new Error(`row ${row} has no rule`);
    return {
      row,
      from: nodeId(r.index_class, row, "index"),
      to: nodeId(r.marker_class, row, "marker"),
      event: eventOf(row),
      supporting: r.supporting ? r.supporting.split(";").filter(Boolean) : [],
      unmatchable: r.unmatchable_role
        ? { role: r.unmatchable_role, reason: r.unmatchable_reason }
        : null,
    };
  });
  const roles = new Map();
  const role = (id) => {
    if (!roles.has(id)) roles.set(id, { index: [], marker: [] });
    return roles.get(id);
  };
  for (const e of edges) {
    role(e.from).index.push(e.row);
    role(e.to).marker.push(e.row);
  }
  const ids = [...roles.keys()].sort();
  const at = layout(
    ids,
    edges.map((e) => [e.from, e.to]),
  );
  return {
    "graph.json": {
      sources: Object.fromEntries(
        Object.entries(files).map(([k, p]) => [p, sha256(text[k])]),
      ),
      canvas: CANVAS,
      nodes: ids.map((id) => ({
        id,
        x: at.get(id)[0],
        y: at.get(id)[1],
        index: roles.get(id).index,
        marker: roles.get(id).marker,
      })),
      edges,
    },
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const here = fileURLToPath(new URL(".", import.meta.url));
  const repoRoot = join(here, "../../..");
  for (const [name, value] of Object.entries(generate(repoRoot)))
    writeFileSync(join(here, "../src/cascade-map", name), serialise(value));
  console.log("cascade map written");
}

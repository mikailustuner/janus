// Feature: experience, Property P19: every recorded fixture decodes; any single mutation (drop a
// required field, wrong type, unknown enum value, array over its bound) is a contract error.
// Task 2.3 (hand-made samples) and task 7.4 (recorded fixtures).
import { describe, expect, it } from "vitest";

import cologne from "@/demo/fixtures/cologne.json";
import istanbul from "@/demo/fixtures/istanbul.json";
import ohio from "@/demo/fixtures/ohio.json";
import { check, fc } from "@/test/fc";

import * as D from "./decode";

type Sample = { name: string; decoder: D.Decoder<unknown>; value: unknown };

function fixtureSamples(name: string, f: typeof istanbul): Sample[] {
  const out: Sample[] = [];
  const add = (n: string, decoder: D.Decoder<unknown>, value: unknown) =>
    out.push({ name: `${name}.${n}`, decoder, value });
  f.items.forEach((it, i) => {
    add(`items[${i}].resolution`, D.resolutionResult, it.resolution);
    if ((it as { scanResolution?: unknown }).scanResolution)
      add(
        `items[${i}].scanResolution`,
        D.resolutionResult,
        (it as { scanResolution: unknown }).scanResolution,
      );
  });
  add("evaluation", D.cascadeResult, f.evaluation);
  for (const [k, v] of Object.entries(f.evidence))
    add(`evidence.${k}`, D.evidenceResolution, v);
  add("memory.snapshot", D.snapshotOut, f.memory.snapshot);
  for (const [k, v] of Object.entries(f.memory.pairs))
    add(`pairs.${k}`, D.pairOut, v);
  add("memory.combination", D.combinationOut, f.memory.combination);
  add("memory.regions", D.regionsOut, f.memory.regions);
  for (const [k, v] of Object.entries(f.memory.shared))
    if (!("error_status" in (v as object))) add(`shared.${k}`, D.sharedOut, v);
  for (const [k, v] of Object.entries(f.notes)) add(`notes.${k}`, D.noteOut, v);
  if (f.doctorForm) add("doctorForm", D.outcomeFormOut, f.doctorForm);
  return out;
}

const samples: Sample[] = [
  ...fixtureSamples("istanbul", istanbul),
  ...fixtureSamples("cologne", cologne as unknown as typeof istanbul),
  ...fixtureSamples("ohio", ohio as unknown as typeof istanbul),
];

type Site = {
  path: (string | number)[];
  decoder: D.Decoder<unknown>;
  parentOptional: boolean;
};

/** Every place in `value` where the decoder checks something, with its decoder. */
function sites(
  decoder: D.Decoder<unknown>,
  value: unknown,
  path: (string | number)[] = [],
  out: Site[] = [],
  optional = false,
): Site[] {
  const m = decoder.meta;
  if (!m) return out;
  if (m.kind === "nullable" || m.kind === "optional") {
    out.push({
      path,
      decoder,
      parentOptional: m.kind === "optional" || optional,
    });
    if (value !== null && value !== undefined)
      sites(m.inner, value, path, out, m.kind === "optional" || optional);
    return out;
  }
  out.push({ path, decoder, parentOptional: optional });
  if (m.kind === "obj" && value && typeof value === "object")
    for (const [k, d] of Object.entries(m.shape))
      sites(d, (value as Record<string, unknown>)[k], [...path, k], out);
  if (m.kind === "arr" && Array.isArray(value))
    value.forEach((v, i) => sites(m.inner, v, [...path, i], out));
  if (m.kind === "record" && value && typeof value === "object")
    for (const [k, v] of Object.entries(value))
      sites(m.inner, v, [...path, k], out, true);
  if (m.kind === "tagged" && value && typeof value === "object") {
    const member = m.members[(value as Record<string, string>)[m.key]!];
    if (member?.meta?.kind === "obj") {
      out.push({
        path: [...path, m.key],
        decoder: D.lit(...Object.keys(m.members)),
        parentOptional: false,
      });
      for (const [k, d] of Object.entries(member.meta.shape))
        if (k !== m.key)
          sites(d, (value as Record<string, unknown>)[k], [...path, k], out);
    }
  }
  return out;
}

function setAt(
  root: unknown,
  path: (string | number)[],
  f: (parent: Record<string | number, unknown>, key: string | number) => void,
) {
  const copy = structuredClone(root);
  let node = copy as Record<string | number, unknown>;
  for (const p of path.slice(0, -1))
    node = node[p] as Record<string | number, unknown>;
  f(node, path[path.length - 1]!);
  return copy;
}

const innerKind = (d: D.Decoder<unknown>): string => {
  const m = d.meta!;
  return m.kind === "nullable" || m.kind === "optional"
    ? innerKind(m.inner)
    : m.kind;
};

describe("recorded fixtures", () => {
  it("every recorded response decodes", () => {
    expect(samples.length).toBeGreaterThan(30);
    for (const s of samples) {
      const r = D.decode(s.decoder, s.value);
      expect(r.ok ? "ok" : (r as { path: string }).path, s.name).toBe("ok");
    }
  });

  const mutationArb = fc.constantFrom(...samples).chain((s) =>
    fc.record({
      sample: fc.constant(s),
      site: fc.constantFrom(
        ...sites(s.decoder, s.value).filter((x) => x.path.length > 0),
      ),
      how: fc.constantFrom("drop", "wrong_type", "unknown_enum", "over_bound"),
    }),
  );

  it("any single mutation is a contract error", () => {
    let applied = 0;
    check(
      fc.property(mutationArb, ({ sample, site, how }) => {
        const kind = innerKind(site.decoder);
        const m = site.decoder.meta!;
        const nullableHere = m.kind === "nullable" || m.kind === "optional";
        let mutated: unknown;
        if (how === "drop") {
          if (
            site.parentOptional ||
            m.kind === "optional" ||
            typeof site.path.at(-1) === "number"
          )
            return;
          mutated = setAt(sample.value, site.path, (p, k) => delete p[k]);
        } else if (how === "wrong_type") {
          const wrong = ["obj", "arr", "record", "tagged"].includes(kind)
            ? 7
            : { wrong: true };
          mutated = setAt(sample.value, site.path, (p, k) => (p[k] = wrong));
        } else if (how === "unknown_enum") {
          if (kind !== "lit") return;
          mutated = setAt(
            sample.value,
            site.path,
            (p, k) => (p[k] = "zz_unknown_value"),
          );
        } else {
          const inner = nullableHere ? m.inner.meta! : m;
          if (inner.kind !== "arr" || inner.max === Infinity) return;
          mutated = setAt(sample.value, site.path, (p, k) => {
            const a = p[k] as unknown[];
            if (Array.isArray(a) && a.length > 0)
              p[k] = Array.from({ length: inner.max + 1 }, () => a[0]);
          });
          if (JSON.stringify(mutated) === JSON.stringify(sample.value)) return;
        }
        const r = D.decode(sample.decoder, mutated);
        applied++;
        expect(r.ok, `${sample.name} ${how} at ${site.path.join(".")}`).toBe(
          false,
        );
      }),
    );
    expect(applied).toBeGreaterThan(20);
  });
});

describe("hand-made samples", () => {
  const source = {
    source_id: "titck",
    run_id: "r",
    region: "TR",
    snapshot_date: "2026-11-06",
  };
  it("accepts a minimal resolution and ignores unknown extra fields", () => {
    const r = D.decode(D.resolutionResult, {
      dataset_version: "a".repeat(64),
      regions_searched: ["TR"],
      sources: [source],
      scan: null,
      notices: [
        {
          code: "no_open_product_database",
          region: "EU",
          country: "DE",
          source_id: null,
          date: null,
        },
      ],
      candidates: [],
      disclaimer: "d",
      future_field: 1,
    });
    expect(r.ok).toBe(true);
  });
  it("rejects an unknown notice code and a wrong candidate kind", () => {
    const base = {
      dataset_version: "a".repeat(64),
      regions_searched: ["TR"],
      sources: [],
      notices: [{ code: "something_new" }],
      candidates: [],
      disclaimer: "d",
    };
    expect(D.decode(D.resolutionResult, base).ok).toBe(false);
    expect(
      D.decode(D.resolutionResult, {
        ...base,
        notices: [],
        candidates: [{ kind: "box" }],
      }).ok,
    ).toBe(false);
  });
  it("reads error bodies leniently and keeps field paths only", () => {
    expect(
      D.errorBody({ error: "invalid_request", fields: ["items.0", 3] }),
    ).toEqual({
      error: "invalid_request",
      fields: ["items.0"],
    });
    expect(D.errorBody("x")).toEqual({ error: null, fields: [] });
  });
});

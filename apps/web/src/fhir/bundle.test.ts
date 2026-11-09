// fhir-export design §5: properties P1–P8 over recorded demo items and generated variations; every
// bundle is checked against the official FHIR R4 JSON schema (offline, committed gzipped).
import { createHash } from "node:crypto";

import { describe, expect, it } from "vitest";

import { demoItems, type Fixture } from "@/demo/client";
import cologne from "@/demo/fixtures/cologne.json";
import istanbul from "@/demo/fixtures/istanbul.json";
import ohio from "@/demo/fixtures/ohio.json";
import type { Item } from "@/store/list";
import { atcLike, month, sentinelBoxName, walk } from "@/test/arbitraries";
import { check, fc } from "@/test/fc";

import {
  ATC_SYSTEM,
  buildBundle,
  CATEGORY_SYSTEM,
  type Bundle,
  DISCLAIMER,
  exportSummary,
  type ExportOptions,
  fileName,
  RXNORM_SYSTEM,
  serialise,
} from "./bundle";
import { fhirSchemaErrors, SCHEMA_SHA256, schemaText } from "./schema/validate";

const fixtures = { istanbul, cologne, ohio } as unknown as Record<
  string,
  Fixture
>;
const DEMO = Object.fromEntries(
  Object.entries(fixtures).map(([k, f]) => [k, demoItems(f)]),
) as Record<string, Item[]>;
const ALL = Object.values(DEMO).flat();

const STATUS_R4 = [
  "active",
  "completed",
  "entered-in-error",
  "intended",
  "stopped",
  "on-hold",
  "unknown",
  "not-taken",
];
const ATC = /^[A-Z][0-9]{2}([A-Z]([A-Z]([0-9]{2})?)?)?$/;
const RXCUI = /^[1-9][0-9]*$/;
const FHIR_DATETIME =
  /^([0-9]([0-9]([0-9][1-9]|[1-9]0)|[1-9]00)|[1-9]000)(-(0[1-9]|1[0-2])(-(0[1-9]|[1-2][0-9]|3[0-1])(T([01][0-9]|2[0-3]):[0-5][0-9]:([0-5][0-9]|60)(\.[0-9]+)?(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00)))?)?)?$/;

const options = (o: Partial<ExportOptions> = {}): ExportOptions => {
  let n = 0;
  return {
    includeProductNames: false,
    demo: false,
    now: new Date("2026-11-09T10:00:00.000Z"),
    newId: () => `00000000-0000-4000-8000-${String(++n).padStart(12, "0")}`,
    englishName: () => null,
    ...o,
  };
};

type Statement = Record<string, unknown> & {
  status: string;
  contained: { resourceType: string; id: string }[];
};
const statements = (b: Bundle) =>
  (b.entry ?? []).map((e) => e.resource as unknown as Statement);

/** R4 rules the JSON schema does not express (cardinality, references, value set). */
function r4Rules(b: Bundle): string[] {
  const out: string[] = [];
  const { strings } = walk(b);
  if (strings.some((s) => s.trim() === "")) out.push("empty string");
  const emptyArray = (v: unknown): boolean =>
    Array.isArray(v)
      ? v.length === 0 || v.some(emptyArray)
      : !!v && typeof v === "object" && Object.values(v).some(emptyArray);
  if (emptyArray(b)) out.push("empty array");
  statements(b).forEach((s, i) => {
    if (!STATUS_R4.includes(s.status)) out.push(`[${i}] status`);
    const meds = ["medicationCodeableConcept", "medicationReference"].filter(
      (k) => k in s,
    );
    if (meds.length !== 1) out.push(`[${i}] medication[x]`);
    const ids = s.contained.map((c) => `#${c.id}`);
    const refs = walk(s).strings.filter((x) => x.startsWith("#"));
    for (const id of ids)
      if (!refs.includes(id)) out.push(`[${i}] ${id} not referenced`);
    for (const r of refs)
      if (!ids.includes(r)) out.push(`[${i}] ${r} not contained`);
  });
  return out;
}

const expectValid = (b: Bundle) => {
  expect(r4Rules(b)).toEqual([]);
  expect(fhirSchemaErrors(JSON.parse(serialise(b)))).toEqual([]);
};

/** Every coding of a bundle. */
function codingsOf(b: Bundle): { system: string; code: string }[] {
  const out: { system: string; code: string }[] = [];
  const visit = (v: unknown) => {
    if (Array.isArray(v)) v.forEach(visit);
    else if (v && typeof v === "object") {
      const o = v as Record<string, unknown>;
      if (Array.isArray(o.coding))
        out.push(...(o.coding as { system: string; code: string }[]));
      for (const [k, x] of Object.entries(o)) if (k !== "category") visit(x);
    }
  };
  visit(b.entry ?? []);
  return out;
}

// A list: demo items in any order, repeated, with any box name, start month and codes.
const itemArb = fc
  .record({
    base: fc.constantFrom(...ALL),
    boxName: sentinelBoxName,
    started: fc.option(month, { nil: null }),
    needsConfirmation: fc.boolean(),
    atc: fc.array(fc.oneof(atcLike, fc.constant("not a code")), {
      maxLength: 3,
    }),
    rxcui: fc.array(fc.oneof(fc.nat(999_999).map(String), fc.constant("x1")), {
      maxLength: 2,
    }),
  })
  .map(({ base, boxName, started, needsConfirmation, atc, rxcui }): Item => {
    const c = structuredClone(base.candidate);
    const src = c.kind === "ingredient" ? c.source : c.source;
    if (c.kind === "ingredient") {
      c.atc_codes = atc.map((code) => ({ code, source: src }));
      c.rxcuis = rxcui;
    } else if (c.ingredients[0]) {
      c.ingredients[0].atc_codes = atc.map((code) => ({ code, source: src }));
      c.ingredients[0].rxcuis = rxcui;
    }
    return { ...base, candidate: c, boxName, started, needsConfirmation };
  });
const listArb = fc
  .array(itemArb, { maxLength: 12 })
  .map((items) => items.map((it, i) => ({ ...it, id: `x${i}` })));

describe("schema file", () => {
  it("is the official R4 schema, unchanged (README)", () => {
    const text = schemaText();
    expect(createHash("sha256").update(text).digest("hex")).toBe(SCHEMA_SHA256);
    const s = JSON.parse(text.toString("utf8"));
    expect(s.$schema).toBe("http://json-schema.org/draft-06/schema#");
    expect(s.id).toBe("http://hl7.org/fhir/json-schema/4.0");
  });

  it("rejects what R4 forbids (the validator really validates)", () => {
    const good = buildBundle(DEMO.cologne!, options());
    expectValid(good);
    const bad = JSON.parse(serialise(good));
    bad.entry[0].resource.effectivePeriod = { start: "2024-13" };
    expect(fhirSchemaErrors(bad)).not.toEqual([]);
    const extra = JSON.parse(serialise(good));
    extra.entry[0].resource.boxName = "x";
    expect(fhirSchemaErrors(extra)).not.toEqual([]);
  });
});

describe("demo patients", () => {
  for (const [patient, items] of Object.entries(DEMO))
    for (const includeProductNames of [false, true])
      it(`${patient}, product names ${includeProductNames}: valid R4`, () => {
        const b = buildBundle(
          items,
          options({ demo: true, includeProductNames }),
        );
        expectValid(b);
        expect(b.entry).toHaveLength(items.length);
        expect(b.meta.security?.[0]?.code).toBe("HTEST");
      });

  it("istanbul: 9 medicines, every ingredient coded", () => {
    expect(exportSummary(DEMO.istanbul!)).toEqual({
      medicines: 9,
      ingredients: 10,
      coded: 10,
    });
  });

  it("a combination is a contained Medication with one coded ingredient each", () => {
    const s = statements(buildBundle(DEMO.istanbul!, options()))[0]!;
    expect(s.medicationReference).toEqual({ reference: "#medication" });
    const med = s.contained.find((c) => c.resourceType === "Medication") as
      | { ingredient: { itemCodeableConcept: { coding: unknown[] } }[] }
      | undefined;
    expect(med?.ingredient).toHaveLength(2);
    expect(med?.ingredient[0]?.itemCodeableConcept.coding).toEqual([
      { system: ATC_SYSTEM, code: "C08CA01" },
      { system: RXNORM_SYSTEM, code: "17767" },
    ]);
  });
});

describe("properties", () => {
  it("P1, P2: one MedicationStatement per item, in list order", () =>
    check(
      fc.property(listArb, (items) => {
        let n = 0;
        const b = buildBundle(items, options({ newId: () => `id-${n++}` }));
        expect(b.type).toBe("collection");
        const entries = b.entry ?? [];
        expect(entries.map((e) => e.resource.resourceType)).toEqual(
          items.map(() => "MedicationStatement"),
        );
        // ids are drawn in order: the bundle first, then entry i gets id-(i+1).
        expect(entries.map((e) => e.resource.id)).toEqual(
          items.map((_, i) => `id-${i + 1}`),
        );
        expect(entries.map((e) => e.fullUrl)).toEqual(
          items.map((_, i) => `urn:uuid:id-${i + 1}`),
        );
      }),
    ));

  it("P3: no box name unless opted in; with the opt-in, each one is there", () =>
    check(
      fc.property(listArb, (items) => {
        const off = walk(buildBundle(items, options())).strings;
        for (const it of items)
          expect(off.some((s) => s.includes(it.boxName))).toBe(false);
        const on = buildBundle(items, options({ includeProductNames: true }));
        statements(on).forEach((s, i) =>
          expect(walk(s).strings).toContain(items[i]!.boxName),
        );
      }),
    ));

  it("P4: start months are valid FHIR dateTimes at month precision, else absent", () =>
    check(
      fc.property(listArb, (items) => {
        statements(buildBundle(items, options())).forEach((s, i) => {
          const start = (s.effectivePeriod as { start?: string } | undefined)
            ?.start;
          expect(start).toBe(items[i]!.started ?? undefined);
          if (start) expect(start).toMatch(FHIR_DATETIME);
          expect(s.dateAsserted).toMatch(FHIR_DATETIME);
        });
      }),
    ));

  it("P5: codings only with the ATC or RxNorm system and a code of that system's shape", () =>
    check(
      fc.property(listArb, (items) => {
        for (const c of codingsOf(buildBundle(items, options()))) {
          expect([ATC_SYSTEM, RXNORM_SYSTEM]).toContain(c.system);
          expect(c.code).toMatch(c.system === ATC_SYSTEM ? ATC : RXCUI);
        }
      }),
    ));

  it("P6: the same list, clock and ids give the same file", () =>
    check(
      fc.property(listArb, fc.boolean(), (items, includeProductNames) => {
        const a = serialise(
          buildBundle(items, options({ includeProductNames })),
        );
        const b = serialise(
          buildBundle(structuredClone(items), options({ includeProductNames })),
        );
        expect(a).toBe(b);
      }),
    ));

  it("P7: every bundle is valid R4 and carries the Janus tag and the disclaimer", () =>
    check(
      fc.property(
        listArb,
        fc.boolean(),
        fc.boolean(),
        (items, includeProductNames, demo) => {
          const b = buildBundle(items, options({ includeProductNames, demo }));
          expectValid(b);
          expect(b.meta.tag[0]?.code).toBe("generated-by-janus");
          statements(b).forEach((s, i) => {
            expect((s.note as { text: string }[])[0]).toEqual({
              text: DISCLAIMER,
            });
            expect((s.note as unknown[]).length).toBe(
              items[i]!.needsConfirmation ? 2 : 1,
            );
            const security = (s.meta as { security?: { code: string }[] })
              .security;
            expect(security?.map((c) => c.code)).toEqual(
              demo ? ["HTEST"] : undefined,
            );
          });
        },
      ),
      { numRuns: 25 },
    ));

  it("P8: the subject carries no personal data; no box code or source id", () =>
    check(
      fc.property(listArb, fc.boolean(), (items, includeProductNames) => {
        const b = buildBundle(items, options({ includeProductNames }));
        const all = walk(b).strings.join("\n");
        for (const it of items) {
          const k = it.sourceKey;
          const code =
            k.kind === "scan" ? k.content : k.kind === "ndc" ? k.ndc : null;
          if (code) expect(all).not.toContain(code);
          expect(all).not.toContain(it.datasetVersion);
          if (it.candidate.kind === "product")
            expect(all).not.toContain(it.candidate.candidate_id);
        }
        for (const s of statements(b)) {
          const patient = s.contained.find((c) => c.resourceType === "Patient");
          expect(patient).toEqual({ resourceType: "Patient", id: "patient" });
          expect(Object.keys(s.subject as object).sort()).toEqual([
            "display",
            "reference",
          ]);
          expect(s.informationSource).toEqual({ reference: "#patient" });
          expect(s.category).toEqual({
            coding: [{ system: CATEGORY_SYSTEM, code: "patientspecified" }],
          });
        }
      }),
    ));
});

describe("file name", () => {
  it("is janus-medicines-YYYY-MM.fhir.json by the UTC month", () => {
    expect(fileName(new Date("2026-11-09T10:00:00Z"))).toBe(
      "janus-medicines-2026-11.fhir.json",
    );
    expect(fileName(new Date("2027-01-01T00:00:00Z"))).toBe(
      "janus-medicines-2027-01.fhir.json",
    );
  });
});

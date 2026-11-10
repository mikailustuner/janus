// Feature: recall-check, web properties W1–W4 (design §8). Validates Req 5.1–5.3, 6.7: the lot
// rule on the device equals the API's rule; the query is an NDC and nothing else; the lot never
// enters a request; only a US product is asked about.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { HttpClient } from "@/api/client";
import type { Candidate, ProductCandidate } from "@/api/contracts";
import { decode } from "@/api/decode";
import { ROUTES, messageKeyFor } from "@/api/errors";
import { outbound } from "@/scan/gs1";
import { validateItem, type SourceKey } from "@/store/list";
import { digits } from "@/test/arbitraries";
import { check, fc } from "@/test/fc";

import { recallCall } from "./client";
import { LOT_EXAMPLES, lotMatch, normaliseLot, usableLot } from "./lot";
import { recallCheckOut } from "./model";
import { layoutsOfNdc10, packageKeysOf, recallQuery } from "./query";

const read = (path: string) =>
  JSON.parse(readFileSync(join(import.meta.dirname, path), "utf8"));
const sample = read("fixtures/check.json");
const ohio = read("../demo/fixtures/ohio.json");
const usProduct = ohio.items[0].resolution.candidates[0] as ProductCandidate;
const ingredient = ohio.items
  .flatMap(
    (i: { resolution: { candidates: Candidate[] } }) => i.resolution.candidates,
  )
  .find((c: Candidate) => c.kind === "ingredient") as Candidate | undefined;

const withPackages = (ndc11: string[]): ProductCandidate => ({
  ...usProduct,
  packages: ndc11.map((k) => ({ ndc_published: k, ndc11: k })),
});

const lotChar = fc.constantFrom(..."ABCXYZabc0123456789-/. @");
const lotArb = fc
  .array(lotChar, { minLength: 1, maxLength: 12 })
  .map((a) => a.join(""));
const code = fc
  .array(fc.constantFrom(..."ABCXYZ0123456789"), {
    minLength: 3,
    maxLength: 10,
  })
  .map((a) => a.join(""));

describe("W1 lot rule on the device", () => {
  it("normalises like the API (shared examples)", () => {
    for (const [written, normalised] of LOT_EXAMPLES)
      expect(normaliseLot(written), written).toBe(normalised);
    // The same table stands in apps/api/janus/recalls/codes.py.
    const py = readFileSync(
      join(import.meta.dirname, "../../../api/janus/recalls/codes.py"),
      "utf8",
    );
    const block = /LOT_EXAMPLES[^=]*=\s*\(([\s\S]*?)\n\)/.exec(py)?.[1] ?? "";
    const pairs = [...block.matchAll(/\("([^"]*)",\s*"([^"]*)"\)/g)].map(
      (m) => [m[1], m[2]],
    );
    expect(pairs).toEqual(LOT_EXAMPLES.map(([a, b]) => [a, b]));
  });

  it("gives ASCII upper-case letters and digits only, and is stable", () => {
    check(
      fc.property(fc.string({ maxLength: 30 }), (s) => {
        const out = normaliseLot(s);
        expect(out).toMatch(/^[0-9A-Z]*$/);
        expect(normaliseLot(out)).toBe(out);
      }),
    );
  });

  it("is listed iff the normalised lot is one of the record's codes", () => {
    check(
      fc.property(lotArb, fc.array(code, { maxLength: 6 }), (lot, codes) => {
        const expected =
          normaliseLot(lot) !== "" && codes.includes(normaliseLot(lot))
            ? "listed"
            : "not_listed";
        expect(lotMatch(lot, codes)).toBe(expected);
        expect(lotMatch(null, codes)).toBe("not_given");
      }),
    );
  });

  it("never matches a longer or a shorter code", () => {
    check(
      fc.property(code, code, (lot, extra) => {
        expect(lotMatch(lot, [lot + extra, extra + lot])).toBe("not_listed");
        expect(lotMatch(lot + extra, [lot])).toBe("not_listed");
        expect(lotMatch(lot.toLowerCase(), [lot])).toBe("listed");
      }),
    );
  });

  it("keeps only a well-formed lot with a letter or a digit", () => {
    expect(usableLot("AB-1234")).toBe("AB-1234");
    for (const bad of [undefined, null, "", "---", "A".repeat(21), "AB 12"])
      expect(usableLot(bad), String(bad)).toBeNull();
  });
});

describe("W2 the lot stays on the device", () => {
  it("is returned beside the scan content and never inside it", () => {
    check(
      fc.property(code, (lot) => {
        const out = outbound(`(01)00312345678906(17)270630(10)ZZ${lot}`);
        expect(out).toEqual({
          kind: "send",
          content: "(01)00312345678906(17)270630",
          gtin: "00312345678906",
          lot: `ZZ${lot}`,
        });
      }),
    );
    // The serial is still dropped, and a lot is not invented.
    const out = outbound("(01)00312345678906(21)ZZSERIAL1");
    expect(out).toMatchObject({ content: "(01)00312345678906", lot: null });
  });

  it("is stored with the list item only when well-formed", () => {
    const item = {
      id: "i",
      sourceKey: { kind: "scan", content: "(01)00312345678906" },
      datasetVersion: "a".repeat(64),
      candidate: usProduct,
      choices: [],
      started: null,
      boxName: "Box",
      needsConfirmation: false,
    };
    expect(validateItem(item)?.lot).toBeUndefined();
    expect(validateItem({ ...item, lot: "AB1234" })?.lot).toBe("AB1234");
    expect(validateItem({ ...item, lot: "A".repeat(21) })).toBeNull();
    expect(validateItem({ ...item, lot: 12 })).toBeNull();
  });

  it("sends the NDC only, and refuses anything else before a request", async () => {
    const bodies: string[] = [];
    const http = new HttpClient(async (_url, init) => {
      bodies.push(String(init.body));
      return new Response(JSON.stringify(sample), { status: 200 });
    });
    const call = recallCall(http);
    const ok = await call("99999012330");
    expect(ok.ok && ok.data.matches).toHaveLength(3);
    expect(bodies).toEqual(['{"ndc":"99999012330"}']);
    for (const bad of ["9999912330", "AB1234", "99999-123-30 AB1234", ""]) {
      const r = await call(bad);
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.error.kind).toBe("build");
    }
    expect(bodies).toHaveLength(1);
  });
});

describe("W3 which NDC is asked", () => {
  const scan = (gtin: string): SourceKey => ({
    kind: "scan",
    content: `(01)${gtin}(17)270630`,
  });

  it("reads the three layouts of ten NDC digits like the API", () => {
    // 4-4-2, 5-3-2, 5-4-1 of janus.resolution.ndc.
    expect(layoutsOfNdc10("0071015523")).toEqual([
      "00071015523",
      "00710015523",
      "00710155203",
    ]);
    expect(packageKeysOf(scan("00300710155236"))).toEqual(
      layoutsOfNdc10("0071015523"),
    );
    expect(packageKeysOf(scan("08690000000012"))).toEqual([]);
    expect(packageKeysOf({ kind: "ndc", ndc: "NDC 0071-0155-23" })).toEqual([
      "00071015523",
    ]);
    expect(packageKeysOf({ kind: "ndc", ndc: "00071015523" })).toEqual([
      "00071015523",
    ]);
    expect(packageKeysOf({ kind: "ndc", ndc: "0071-0155" })).toEqual([]);
  });

  it("asks the package when the source names one, else the product code", () => {
    const c = withPackages(["00071015523", "00071015540"]);
    expect(recallQuery(c, scan("00300710155236"))).toEqual({
      ndc: "00071015523",
      level: "package",
    });
    expect(recallQuery(c, { kind: "ndc", ndc: "0071-0155-40" })).toEqual({
      ndc: "00071015540",
      level: "package",
    });
    const byName: SourceKey = {
      kind: "search",
      query: "atorvastatin",
      region: "US",
      pick: { kind: "product", sourceId: "openfda_ndc", productName: "X" },
    };
    expect(recallQuery(c, byName)).toEqual({
      ndc: "00071-0155",
      level: "product",
    });
  });

  it("asks nothing for other regions, ingredients, or mixed product codes", () => {
    const c = withPackages(["00071015523"]);
    const key: SourceKey = { kind: "ndc", ndc: "0071-0155-23" };
    expect(recallQuery({ ...c, region: "TR" }, key)).toBeNull();
    expect(recallQuery({ ...c, region: "EU" }, key)).toBeNull();
    expect(recallQuery(withPackages([]), key)).toBeNull();
    if (ingredient) expect(recallQuery(ingredient, key)).toBeNull();
    const mixed = withPackages(["00071015523", "00071015623"]);
    expect(recallQuery(mixed, { kind: "ndc", ndc: "0071-0199-23" })).toBeNull();
    expect(recallQuery(mixed, key)?.level).toBe("package");
  });

  it("always builds an NDC the API accepts, from the candidate's own packages", () => {
    check(
      fc.property(
        fc.array(digits(11), { minLength: 1, maxLength: 4 }),
        fc.oneof(digits(14), digits(11), digits(10)),
        fc.boolean(),
        (keys, typed, asScan) => {
          const q = recallQuery(
            withPackages(keys),
            asScan ? scan(typed) : { kind: "ndc", ndc: typed },
          );
          if (q === null) return;
          expect(q.ndc).toMatch(/^(\d{11}|\d{5}-\d{4})$/);
          if (q.level === "package") expect(keys).toContain(q.ndc);
          else
            expect(keys.map((k) => k.slice(0, 9))).toContain(
              q.ndc.replace("-", ""),
            );
        },
      ),
    );
  });
});

describe("W4 contract and errors", () => {
  it("decodes the API's answer and refuses a changed one", () => {
    const ok = decode(recallCheckOut, sample);
    expect(ok.ok).toBe(true);
    for (const broken of [
      { ...sample, region: "EU" },
      { ...sample, notices: ["all_clear"] },
      {
        ...sample,
        matches: [{ ...sample.matches[0], ndc_match: "name" }],
      },
      {
        ...sample,
        matches: [
          { ...sample.matches[0], record_url: "https://example.org/x" },
        ],
      },
      { ...sample, matches: [{ ...sample.matches[0], lot_codes: ["ab"] }] },
      { ...sample, source: { ...sample.source, snapshot_date: "soon" } },
    ])
      expect(decode(recallCheckOut, broken).ok).toBe(false);
  });

  it("maps the route's errors to catalogue keys", () => {
    expect(ROUTES).toContain("recalls/check");
    expect(messageKeyFor("recalls/check", 503, "recalls_unavailable")).toBe(
      "Recall.errors.unavailable",
    );
    expect(messageKeyFor("recalls/check", 422, "ndc_malformed")).toBe(
      "Errors.generic",
    );
    expect(messageKeyFor("recalls/check", 422, "invalid_request")).toBe(
      "Errors.client_defect",
    );
  });
});

// Feature: experience, Property P1: the outbound filter keeps exactly (01), (17), (712), in that
// order, and nothing of (21), (10) or any other AI (Req 10.2, 10.3, 23.1). Task 13.2: zxing-wasm
// decodes the demo sheet's DataMatrix codes in node, and the filtered content has no (21).
import { describe, expect, it } from "vitest";
import { readBarcodes } from "zxing-wasm/reader";
import { writeBarcode } from "zxing-wasm/writer";

import codes from "@/demo/codes.svg.json";
import { checkDigit } from "@/demo/codes";
import { digits } from "@/test/arbitraries";
import { check, fc } from "@/test/fc";

import { classifyTyped, outbound, parseElementString } from "./gs1";

const gtin14 = digits(13).map((d) => d + checkDigit(d));
const serial = fc.stringMatching(/^[A-Z0-9]{4,20}$/).map((s) => `ZZS${s}`);
const lot = fc.stringMatching(/^[A-Z0-9]{4,15}$/).map((s) => `ZZL${s}`);
const yymmdd = fc
  .tuple(
    fc.integer({ min: 20, max: 40 }),
    fc.integer({ min: 1, max: 12 }),
    fc.integer({ min: 0, max: 28 }),
  )
  .map(
    ([y, m, d]) =>
      `${y}${String(m).padStart(2, "0")}${String(d).padStart(2, "0")}`,
  );
const cn = fc.stringMatching(/^[0-9]{6,9}$/);

type Field = { ai: string; value: string; variable: boolean };
const fieldsArb = fc
  .record({
    gtin: gtin14,
    expiry: fc.option(yymmdd, { nil: undefined }),
    national: fc.option(cn, { nil: undefined }),
    serial: fc.option(serial, { nil: undefined }),
    lot: fc.option(lot, { nil: undefined }),
    other: fc.option(
      fc.constantFrom("240", "710", "711", "713", "714", "716"),
      { nil: undefined },
    ),
    otherValue: fc.stringMatching(/^ZZO[A-Z0-9]{2,10}$/),
    order: fc.array(fc.nat(), { minLength: 7, maxLength: 7 }),
  })
  .map((r) => {
    const fields: Field[] = [{ ai: "01", value: r.gtin, variable: false }];
    if (r.expiry) fields.push({ ai: "17", value: r.expiry, variable: false });
    if (r.national)
      fields.push({ ai: "712", value: r.national, variable: true });
    if (r.serial) fields.push({ ai: "21", value: r.serial, variable: true });
    if (r.lot) fields.push({ ai: "10", value: r.lot, variable: true });
    if (r.other)
      fields.push({ ai: r.other, value: r.otherValue, variable: true });
    const shuffled = fields
      .map((f, i) => ({ f, k: r.order[i] ?? i }))
      .sort((a, b) => a.k - b.k)
      .map((x) => x.f);
    return { r, fields: shuffled };
  });

function encode(
  fields: Field[],
  form: "paren" | "fnc1",
  symbology: boolean,
): string {
  if (form === "paren")
    return (
      (symbology ? "]d2" : "") +
      fields.map((f) => `(${f.ai})${f.value}`).join("")
    );
  let s = symbology ? "]d2" : "";
  fields.forEach((f, i) => {
    s += f.ai + f.value;
    if (f.variable && i < fields.length - 1) s += "\x1d";
  });
  return s;
}

describe("P1 outbound filter", () => {
  it("keeps exactly (01), (17), (712) in that order and nothing else", () => {
    check(
      fc.property(
        fieldsArb,
        fc.constantFrom("paren" as const, "fnc1" as const),
        fc.boolean(),
        ({ r, fields }, form, sym) => {
          const out = outbound(encode(fields, form, sym));
          expect(out.kind).toBe("send");
          if (out.kind !== "send") return;
          let expected = `(01)${r.gtin}`;
          if (r.expiry) expected += `(17)${r.expiry}`;
          if (r.national) expected += `(712)${r.national}`;
          expect(out.content).toBe(expected);
          for (const sentinel of [r.serial, r.lot, r.otherValue])
            if (sentinel && !expected.includes(sentinel))
              expect(out.content).not.toContain(sentinel);
          expect(out.content).not.toMatch(/\((21|10|240|71[0-1346])\)/);
        },
      ),
    );
  });
  it("passes valid bare GTINs unchanged and refuses invalid ones", () => {
    check(
      fc.property(fc.constantFrom(7, 11, 12, 13), fc.nat(), (len, seed) => {
        const body = String(seed).padStart(len, "1").slice(0, len);
        const g = body + checkDigit(body);
        expect(outbound(g)).toEqual({ kind: "send", content: g, gtin: g });
        const wrong = body + String((Number(checkDigit(body)) + 1) % 10);
        expect(outbound(wrong)).toEqual({ kind: "unreadable" });
      }),
    );
  });
  it("sends only a valid leading (01) when the rest cannot be parsed, else nothing", () => {
    check(
      fc.property(gtin14, serial, (g, s) => {
        expect(outbound(`(01)${g}(21${s}`)).toEqual({
          kind: "send",
          content: `(01)${g}`,
          gtin: g,
        });
        expect(outbound(`(21)${s}`)).toEqual({ kind: "unreadable" });
        expect(outbound(`garbage ${s}`)).toEqual({ kind: "unreadable" });
      }),
    );
    expect(parseElementString("(01)1(01)2")).toBeNull();
  });
});

describe("typed input (Req 11.4)", () => {
  it("never sends national codes as codes", () => {
    for (const t of [
      "3400936",
      "PZN-12345678",
      "PZN 1234567",
      "654321",
      "6543210",
    ])
      expect(classifyTyped(t).kind).toBe("national_code");
    expect(classifyTyped("NDC 0069-0150-01")).toEqual({
      kind: "ndc",
      ndc: "0069-0150-01",
    });
    expect(classifyTyped("amlodipine")).toEqual({
      kind: "search",
      query: "amlodipine",
    });
    expect(classifyTyped("x").kind).toBe("invalid");
    const cip13 = "340093643210" + checkDigit("340093643210");
    expect(classifyTyped(cip13)).toEqual({ kind: "scan", content: cip13 });
  });
});

describe("13.2 zxing-wasm decodes the demo sheet", () => {
  it("reads every demo DataMatrix as GS1 and drops the serial", async () => {
    for (const c of Object.values(codes as Record<string, { text: string }>)) {
      const w = await writeBarcode(c.text, {
        format: "DataMatrix",
        options: "gs1",
        scale: 4,
      });
      const [read] = await readBarcodes(w.image!, { formats: ["DataMatrix"] });
      expect(read?.contentType).toBe("GS1");
      const out = outbound(read!.text);
      expect(out.kind).toBe("send");
      if (out.kind === "send") {
        expect(out.content).not.toContain("(21)");
        expect(out.content).not.toContain("DEMO");
        expect(out.content.startsWith("(01)0295268")).toBe(true);
      }
    }
  });
});

describe("typed element strings (safety audit A8)", () => {
  it("never send a typed serial or lot as search text", () => {
    check(
      fc.property(
        fieldsArb,
        fc.constantFrom("paren" as const, "fnc1" as const),
        ({ r, fields }, form) => {
          const typed = classifyTyped(encode(fields, form, false));
          if (form === "fnc1" && !/\x1d/.test(encode(fields, form, false)))
            return; // bare digits: other rules
          expect(typed.kind).toBe("scan");
          if (typed.kind === "scan")
            for (const sentinel of [r.serial, r.lot, r.otherValue])
              if (sentinel) expect(typed.content).not.toContain(sentinel);
        },
      ),
    );
    const gtin = "0" + "869000000001" + checkDigit("0869000000001".slice(1));
    expect(classifyTyped(`GTIN ${gtin} SN ZZSERIAL123 LOT ZZLOT9`).kind).toBe(
      "scan",
    );
    expect(classifyTyped("SN 12345678 LOT 4455").kind).toBe("national_code");
  });
});

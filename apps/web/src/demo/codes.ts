/**
 * Demo codes (experience design §13.2, DP11, P15). GTIN-13 in the GS1 restricted-circulation
 * range: prefix `29` + `5268` + a 6-digit product number + check digit (GTIN-14 `0295268…`). No
 * medicine source uses prefixes 20–29 (TR 868/869, US 03, FR 034, ES 084, DE 400–440). Demo NDC
 * shapes start with `0295-268`. Detection runs on every input path before any request.
 */
import type { PatientId } from "./session";

export const DEMO_PREFIX = "295268";

/** GS1 mod-10 check digit of the digits before it. */
export function checkDigit(body: string): string {
  let sum = 0;
  const n = body.length;
  for (let i = 0; i < n; i++)
    sum += Number(body[n - 1 - i]) * (i % 2 === 0 ? 3 : 1);
  return String((10 - (sum % 10)) % 10);
}

export function validGtin(digits: string): boolean {
  if (!/^(\d{8}|\d{12}|\d{13}|\d{14})$/.test(digits)) return false;
  return checkDigit(digits.slice(0, -1)) === digits.slice(-1);
}

export function demoGtin13(product: number): string {
  const body = DEMO_PREFIX + String(product).padStart(6, "0");
  return body + checkDigit(body);
}

/** True for a valid demo GTIN-13 or its GTIN-14 form. */
export function isDemoGtin(code: string): boolean {
  const d = code.length === 14 && code.startsWith("0") ? code.slice(1) : code;
  return d.length === 13 && d.startsWith(DEMO_PREFIX) && validGtin(d);
}

/** Demo products: patient and item index by product number (offsets of scripts/record-demo.mjs). */
const OFFSETS: Record<PatientId, { offset: number; count: number }> = {
  istanbul: { offset: 0, count: 9 },
  cologne: { offset: 10, count: 4 },
  ohio: { offset: 20, count: 4 },
};

export interface DemoRef {
  patient: PatientId;
  index: number;
}

export function demoRef(code: string): DemoRef | null {
  if (!isDemoGtin(code)) return null;
  const d = code.length === 14 ? code.slice(1) : code;
  const product = Number(d.slice(6, 12));
  for (const [patient, { offset, count }] of Object.entries(OFFSETS) as [
    PatientId,
    (typeof OFFSETS)[PatientId],
  ][])
    if (product > offset && product <= offset + count)
      return { patient, index: product - offset - 1 };
  return null;
}

export const DEMO_NDC = /\b0295-268(\d)-\d{2}\b/;

/**
 * Detects a demo code in any input: decoded barcode text (FNC1 or parenthesised GS1, bare
 * digits), typed digits, or a recognised label line with a demo NDC. Pure, no request.
 */
export function detectDemo(text: string): DemoRef | null {
  const ndc = DEMO_NDC.exec(text);
  if (ndc) {
    const index = Number(ndc[1]);
    return index < OFFSETS.ohio.count ? { patient: "ohio", index } : null;
  }
  const clean = text.replace(/^\][A-Za-z]\d/, "");
  const ai01 = /(?:\(01\)|^01|\x1d01)(\d{14})/.exec(clean);
  if (ai01) return demoRef(ai01[1]!);
  const digits = clean.replace(/[\s-]/g, "");
  if (/^\d{13,14}$/.test(digits)) return demoRef(digits);
  return null;
}

/** Every demo product code, for the printable sheet. */
export function allDemoCodes(): {
  patient: PatientId;
  index: number;
  gtin13: string;
}[] {
  return (
    Object.entries(OFFSETS) as [PatientId, (typeof OFFSETS)[PatientId]][]
  ).flatMap(([patient, { offset, count }]) =>
    Array.from({ length: count }, (_, index) => ({
      patient,
      index,
      gtin13: demoGtin13(offset + index + 1),
    })),
  );
}

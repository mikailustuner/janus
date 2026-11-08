/**
 * GS1 element-string parser and outbound filter (experience design §6.2, Req 10.2–10.3, P1).
 *
 * Only (01) GTIN, (17) expiry and (712) national product number ever leave this module, in that
 * order, as `(01)…(17)…(712)…`. Serial (21), lot (10) and every other AI are dropped here and are
 * never stored or logged. A bare GTIN-8/12/13/14 with a valid check digit passes as digits.
 */
import { validGtin } from "@/demo/codes";

const GS = "\x1d";

/** Length of the AI that starts `s` (2, 3 or 4 digits), from the GS1 general specification. */
function aiLength(s: string): number | null {
  const p = s.slice(0, 2);
  if (!/^\d\d$/.test(p)) return null;
  const n = Number(p);
  if (n <= 22) return 2;
  if (
    n === 23 ||
    n === 24 ||
    n === 25 ||
    n === 40 ||
    n === 41 ||
    n === 42 ||
    n === 71
  )
    return 3;
  if (
    (n >= 31 && n <= 36) ||
    n === 39 ||
    n === 70 ||
    n === 72 ||
    (n >= 80 && n <= 82)
  )
    return 4;
  if (n >= 90) return 2;
  return null;
}

/** Fixed data lengths (predefined-length AIs); others run to FNC1 or the end. */
function fixedLength(ai: string): number | null {
  if (ai === "00") return 18;
  if (/^0[1-3]$/.test(ai)) return 14;
  if (/^1[1-7]$/.test(ai)) return 6;
  if (ai === "20") return 2;
  if (/^3[1-6]\d\d$/.test(ai)) return 6;
  if (/^41\d$/.test(ai)) return 13;
  return null;
}

export type ParsedGs1 = Map<string, string>;

/** Parses a decoded element string (FNC1 or parenthesised, optional symbology id); null if not GS1. */
export function parseElementString(raw: string): ParsedGs1 | null {
  let s = raw.replace(/^\][A-Za-z]\d/, "");
  const out: ParsedGs1 = new Map();
  if (s.startsWith("(")) {
    const re = /\((\d{2,4})\)([^(]*)/gy;
    let m: RegExpExecArray | null;
    let consumed = 0;
    while ((m = re.exec(s))) {
      if (out.has(m[1]!)) return null;
      out.set(m[1]!, m[2]!.replaceAll(GS, ""));
      consumed = re.lastIndex;
    }
    return consumed === s.length && out.size > 0 ? out : null;
  }
  if (s.startsWith(GS)) s = s.slice(1);
  while (s.length > 0) {
    const len = aiLength(s);
    if (len === null || s.length < len) return null;
    const ai = s.slice(0, len);
    s = s.slice(len);
    const fixed = fixedLength(ai);
    let value: string;
    if (fixed !== null) {
      if (s.length < fixed) return null;
      value = s.slice(0, fixed);
      s = s.slice(fixed);
      if (s.startsWith(GS)) s = s.slice(1);
    } else {
      const end = s.indexOf(GS);
      value = end < 0 ? s : s.slice(0, end);
      s = end < 0 ? "" : s.slice(end + 1);
    }
    if (out.has(ai) || value.length === 0) return null;
    out.set(ai, value);
  }
  return out.size > 0 ? out : null;
}

export type Outbound =
  | { kind: "send"; content: string; gtin: string | null }
  | { kind: "unreadable" };

/** The content sent to `POST /resolve/scan`: (01), (17), (712) only, or bare GTIN digits. */
export function outbound(raw: string): Outbound {
  const text = raw.trim();
  const digits = text.replace(/^\][A-Za-z]\d/, "");
  if (/^(\d{8}|\d{12}|\d{13}|\d{14})$/.test(digits))
    return validGtin(digits)
      ? { kind: "send", content: digits, gtin: digits }
      : { kind: "unreadable" };
  const parsed = parseElementString(text);
  if (parsed) {
    const gtin = parsed.get("01");
    if (!gtin || !/^\d{14}$/.test(gtin) || !validGtin(gtin))
      return { kind: "unreadable" };
    let content = `(01)${gtin}`;
    const exp = parsed.get("17");
    if (exp && /^\d{6}$/.test(exp)) content += `(17)${exp}`;
    const cn = parsed.get("712");
    if (cn && /^[\x21-\x7e]{1,20}$/.test(cn)) content += `(712)${cn}`;
    return { kind: "send", content, gtin };
  }
  // Not parseable, but a leading (01) with a valid GTIN: send that alone.
  const lead = /^(?:\][A-Za-z]\d)?(?:\(01\)|\x1d?01)(\d{14})/.exec(text);
  if (lead && validGtin(lead[1]!))
    return { kind: "send", content: `(01)${lead[1]}`, gtin: lead[1]! };
  return { kind: "unreadable" };
}

export type Typed =
  | { kind: "scan"; content: string }
  | { kind: "ndc"; ndc: string }
  | { kind: "national_code" }
  | { kind: "search"; query: string }
  | { kind: "invalid" };

/** Typed input (design §6.3, Req 11.4): codes by shape; national non-GTIN codes are never sent as codes. */
export function classifyTyped(input: string): Typed {
  const t = input.trim();
  const compact = t.replace(/[\s]/g, "");
  if (/^(\d{8}|\d{12}|\d{13}|\d{14})$/.test(compact) && validGtin(compact))
    return { kind: "scan", content: compact };
  const ndc = /^(?:NDC[:\s]*)?(\d{4,5}-\d{3,4}-\d{1,2})$/i.exec(t);
  if (ndc) return { kind: "ndc", ndc: ndc[1]! };
  const ndcDigits = /^NDC[:\s]*(\d{10,11})$/i.exec(t);
  if (ndcDigits) return { kind: "ndc", ndc: ndcDigits[1]! };
  if (/^(PZN[-\s]?\d{7,8}|\d{6,7}(\.\d)?)$/i.test(compact))
    return { kind: "national_code" };
  if (t.length >= 2 && t.length <= 100) return { kind: "search", query: t };
  return { kind: "invalid" };
}

/**
 * Which NDC the recall check asks about for a confirmed medicine (recall-check design §9). Pure.
 *
 * Only a US product has an answer. When the scan or the typed NDC names one package of the
 * product, that package's 11-digit key is asked (a `package` match is possible); otherwise the
 * hyphenated 9-digit product code, which finds every record that names the product or any of its
 * packages. Nothing but the NDC is ever part of the request.
 */
import type { Candidate } from "@/api/contracts";
import type { SourceKey } from "@/store/list";

export interface RecallQuery {
  ndc: string;
  level: "package" | "product";
}

/** The canonical 11-digit keys ten plain NDC digits can stand for (4-4-2, 5-3-2, 5-4-1). */
export function layoutsOfNdc10(d: string): string[] {
  return [
    `0${d}`,
    `${d.slice(0, 5)}0${d.slice(5)}`,
    `${d.slice(0, 9)}0${d.slice(9)}`,
  ];
}

/** The 11-digit keys a source key can name: from an NDC GTIN, or from an NDC as typed. */
export function packageKeysOf(source: SourceKey): string[] {
  if (source.kind === "scan") {
    const gtin = /^(?:\(01\))?(\d{8,14})/.exec(source.content)?.[1];
    const ndc10 = gtin
      ? /^[0-8]03(\d{10})\d$/.exec(gtin.padStart(14, "0"))?.[1]
      : undefined;
    return ndc10 ? layoutsOfNdc10(ndc10) : [];
  }
  if (source.kind !== "ndc") return [];
  const text = source.ndc.replace(/\s/g, "").replace(/^NDC:?/i, "");
  if (/^\d{11}$/.test(text)) return [text];
  if (/^\d{10}$/.test(text)) return layoutsOfNdc10(text);
  const parts = text.split("-");
  if (parts.length !== 3 || !parts.every((p) => /^\d+$/.test(p))) return [];
  const [a, b, c] = parts as [string, string, string];
  if (a.length > 5 || b.length > 4 || c.length > 2) return [];
  return [a.padStart(5, "0") + b.padStart(4, "0") + c.padStart(2, "0")];
}

export function recallQuery(
  candidate: Candidate,
  source: SourceKey,
): RecallQuery | null {
  if (candidate.kind !== "product" || candidate.region !== "US") return null;
  const keys = candidate.packages
    .map((p) => p.ndc11)
    .filter((k) => /^\d{11}$/.test(k));
  if (keys.length === 0) return null;
  const named = packageKeysOf(source).filter((k) => keys.includes(k));
  if (named.length === 1) return { ndc: named[0]!, level: "package" };
  // One product code only: packages of different products under one candidate are not guessed.
  const products = new Set(keys.map((k) => k.slice(0, 9)));
  if (products.size !== 1) return null;
  const product = [...products][0]!;
  return {
    ndc: `${product.slice(0, 5)}-${product.slice(5)}`,
    level: "product",
  };
}

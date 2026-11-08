/**
 * QR code of the outcome loop (experience design §10.3, DP7, Req 18.2, P25): level M, byte mode,
 * version at most 25, drawn as one SVG path with a 4-module quiet zone. The token is only in the
 * URL fragment. In demo the address is `<origin>/o#demo-<patient>`.
 */
import QRCode from "qrcode";

export const MAX_VERSION = 25;
export const QUIET = 4;

export interface Qr {
  version: number;
  size: number; // modules, without the quiet zone
  path: string; // SVG path in module units, quiet zone included
  modules: boolean[][];
}

export function makeQr(url: string): Qr | null {
  const code = QRCode.create(
    [{ data: new TextEncoder().encode(url), mode: "byte" }],
    {
      errorCorrectionLevel: "M",
    },
  );
  if (code.version > MAX_VERSION) return null;
  const n = code.modules.size;
  const modules: boolean[][] = [];
  let path = "";
  for (let y = 0; y < n; y++) {
    const row: boolean[] = [];
    for (let x = 0; x < n; x++) {
      const on = !!code.modules.get(y, x);
      row.push(on);
      if (on) path += `M${x + QUIET} ${y + QUIET}h1v1h-1z`;
    }
    modules.push(row);
  }
  return { version: code.version, size: n, path, modules };
}

/** The address of the doctor page: the API's `qr_url`, else this origin (DP19). */
export function qrAddress(
  qrUrl: string | null,
  origin: string,
  token: string,
): string {
  return qrUrl ?? `${origin}/o#${token}`;
}

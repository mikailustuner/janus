/**
 * Which reading of a label photo is used (ocr-first design §4, Req 4.3). A photo is read as it
 * is; only when that reading names no ingredient and no NDC and the recogniser itself reports low
 * confidence is the photo read again turned by a quarter, three quarters and a half turn (a box
 * photographed on its side). Pure: the caller supplies the reading function, so the app and the
 * evaluation share the rule.
 */
export interface Pass {
  /** Mean word confidence reported by the recogniser, 0–100. */
  confidence: number;
  lines: { text: string; words: string[] }[];
}

/** Quarter turns applied to the photo before reading. */
export type Turns = 0 | 1 | 2 | 3;

/** Below this confidence a reading without a candidate is tried again turned. */
export const RETRY_BELOW = 75;

export async function readLabel(
  read: (turns: Turns) => Promise<Pass>,
  useful: (pass: Pass) => boolean,
): Promise<Pass> {
  const first = await read(0);
  if (useful(first) || first.confidence >= RETRY_BELOW) return first;
  let best = first;
  for (const turns of [1, 3, 2] as const) {
    const pass = await read(turns);
    if (useful(pass)) return pass;
    if (pass.confidence > best.confidence) best = pass;
  }
  return best;
}

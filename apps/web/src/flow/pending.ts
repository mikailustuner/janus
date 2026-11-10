"use client";
/**
 * The resolution waiting for confirmation (design §3: "last resolution (memory)"): held in memory
 * only, with the source key the item will keep for re-resolution (Req 14.2). Never stored.
 */
import { useSyncExternalStore } from "react";

import type { ResolutionResult } from "@/api/contracts";

export interface Pending {
  resolution: ResolutionResult;
  /** How the candidates were found; a search key gets its pick when the user chooses. */
  source:
    | { kind: "scan"; content: string }
    | { kind: "ndc"; ndc: string }
    | { kind: "search"; query: string; region: "TR" | "US" | "EU" | null };
  typed: string | null;
  /** The lot of the scanned box, AI (10): kept on the device only (recall-check Req 5). */
  lot: string | null;
  /** Set when a list item is confirmed again after a dataset change. */
  replaces: string | null;
}

let current: Pending | null = null;
const listeners = new Set<() => void>();

export function setPending(p: Pending | null) {
  current = p;
  for (const l of listeners) l();
}

export function usePending(): Pending | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => current,
    () => null,
  );
}

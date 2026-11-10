"use client";
/**
 * The recall answer for one NDC, with a retry (recall-check design §9). Kept in memory only,
 * by NDC; never persisted. Successful answers are reused for the session.
 */
import { useEffect, useState } from "react";

import type { ApiError } from "@/api/errors";

import { liveRecall, type RecallCall } from "./client";
import type { RecallCheckOut } from "./model";

export type RecallState =
  | { status: "loading" }
  | { status: "ok"; data: RecallCheckOut }
  | { status: "error"; error: ApiError };

const cache = new Map<string, RecallCheckOut>();

export function useRecall(
  ndc: string,
  call: RecallCall = liveRecall,
): RecallState & { retry: () => void } {
  const [state, setState] = useState<{
    ndc: string;
    value: RecallState;
  } | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    if (cache.has(ndc)) return;
    let live = true;
    call(ndc).then((r) => {
      if (r.ok) cache.set(ndc, r.data);
      if (live)
        setState({
          ndc,
          value: r.ok
            ? { status: "ok", data: r.data }
            : { status: "error", error: r.error },
        });
    });
    return () => {
      live = false;
    };
  }, [ndc, call, n]);
  const retry = () => {
    setState(null);
    setN((x) => x + 1);
  };
  const cached = cache.get(ndc);
  if (cached) return { status: "ok", data: cached, retry };
  if (state && state.ndc === ndc) return { ...state.value, retry };
  return { status: "loading", retry };
}

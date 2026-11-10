"use client";
/**
 * The safety check answer for one evaluation input, with a retry (safety-check design §8). Kept
 * in memory only, by input; never persisted. A list change gives a new input, so an older answer
 * is never shown as current.
 */
import { useEffect, useState } from "react";

import type { ApiError } from "@/api/errors";
import type { EvaluateIn } from "@/api/contracts";
import { inputKey } from "@/flow/evaluate";

import { liveSafety, type SafetyCall } from "./client";
import type { SafetyCheckOut } from "./model";

export type SafetyState =
  | { status: "loading" }
  | { status: "ok"; data: SafetyCheckOut }
  | { status: "error"; error: ApiError };

const cache = new Map<string, SafetyCheckOut>();

export function useSafety(
  body: EvaluateIn,
  call: SafetyCall = liveSafety,
): SafetyState & { retry: () => void } {
  const key = inputKey(body);
  const [state, setState] = useState<{
    key: string;
    value: SafetyState;
  } | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    if (cache.has(key)) return;
    let live = true;
    call(JSON.parse(key) as EvaluateIn).then((r) => {
      if (r.ok) cache.set(key, r.data);
      if (live)
        setState({
          key,
          value: r.ok
            ? { status: "ok", data: r.data }
            : { status: "error", error: r.error },
        });
    });
    return () => {
      live = false;
    };
  }, [key, call, n]);
  const retry = () => {
    setState(null);
    setN((x) => x + 1);
  };
  const cached = cache.get(key);
  if (cached) return { status: "ok", data: cached, retry };
  if (state && state.key === key) return { ...state.value, retry };
  return { status: "loading", retry };
}

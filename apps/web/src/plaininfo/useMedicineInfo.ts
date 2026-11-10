"use client";
/**
 * The answer for one medicine, with a retry (plain-medicine-info design §8). Kept in memory
 * only, by request; never persisted. Successful answers are reused for the session.
 */
import { useEffect, useState } from "react";

import type { ApiError } from "@/api/errors";

import type { InfoCall } from "./client";
import type { MedicineInfoIn, MedicineInfoOut } from "./model";
import { queryKey } from "./query";

export type InfoState =
  | { status: "loading" }
  | { status: "ok"; data: MedicineInfoOut }
  | { status: "error"; error: ApiError };

const cache = new Map<string, MedicineInfoOut>();

export function useMedicineInfo(
  body: MedicineInfoIn | null,
  call: InfoCall,
  demo: boolean,
): (InfoState | { status: "nothing" }) & { retry: () => void } {
  const key = body ? `${demo ? "demo" : "live"}:${queryKey(body)}` : null;
  const [state, setState] = useState<{ key: string; value: InfoState } | null>(
    null,
  );
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!body || !key || cache.has(key)) return;
    let live = true;
    call(body).then((r) => {
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
    // `key` stands for `body`: the same request is the same key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, call, n]);
  const retry = () => {
    setState(null);
    setN((x) => x + 1);
  };
  if (!key) return { status: "nothing", retry };
  const cached = cache.get(key);
  if (cached) return { status: "ok", data: cached, retry };
  if (state && state.key === key) return { ...state.value, retry };
  return { status: "loading", retry };
}

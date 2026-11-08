"use client";
/** One idempotent read call with loading / error / ok state and a retry (design §9). */
import { useCallback, useEffect, useState } from "react";

import type { Result } from "@/api/client";
import type { ApiError } from "@/api/errors";

export type CallState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ok"; data: T }
  | { status: "skip" };

export function useCall<T>(
  run: (() => Promise<Result<T>>) | null,
  deps: unknown[],
): CallState<T> & { retry: () => void } {
  // The answer is kept with the request it belongs to, so a stale answer is never shown.
  const [answer, setAnswer] = useState<{
    key: string;
    state: CallState<T>;
  } | null>(null);
  const [n, setN] = useState(0);
  const retry = useCallback(() => setN((x) => x + 1), []);
  const key = JSON.stringify([
    deps.map((d) => (typeof d === "object" ? String(!!d) : d)),
    n,
  ]);
  useEffect(() => {
    if (!run) return;
    let live = true;
    Promise.resolve()
      .then(run)
      .then(
        (r) =>
          live &&
          setAnswer({
            key,
            state: r.ok
              ? { status: "ok", data: r.data }
              : { status: "error", error: r.error },
          }),
        // A body the builders refuse is a client defect (never sent).
        () =>
          live &&
          setAnswer({
            key,
            state: {
              status: "error",
              error: {
                kind: "build",
                route: "evidence/resolve",
                messageKey: "Errors.client_defect",
              },
            },
          }),
      );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, !!run]);
  if (!run) return { status: "skip", retry };
  if (!answer || answer.key !== key) return { status: "loading", retry };
  return { ...answer.state, retry };
}

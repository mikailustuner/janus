"use client";
/**
 * Runs `POST /cascades/evaluate` for the current list once per evaluation input and keeps the
 * result in memory only (DP29). A list change gives a new input, so an older result is never
 * shown as current (Req 13.5).
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import type { ApiError } from "@/api/errors";
import type { CascadeResult, EvaluateIn } from "@/api/contracts";

import { inputKey, toEvaluateIn, type EvaluateInput } from "./evaluate";
import { resultCache, type Session } from "./janus";

export type EvaluationState =
  | { status: "idle" | "loading" }
  | {
      status: "blocked";
      reason: Extract<EvaluateInput, { ok: false }>["reason"];
    }
  | { status: "error"; error: ApiError }
  | { status: "ok"; result: CascadeResult; input: EvaluateIn };

export function useEvaluation(
  session: Session,
): EvaluationState & { retry: () => void } {
  const [attempt, setAttempt] = useState(0);
  const [answer, setAnswer] = useState<{
    key: string;
    error: ApiError | null;
  } | null>(null);
  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  const { ready, client, items } = session;
  const built = useMemo(
    () => (ready ? toEvaluateIn(items) : null),
    [ready, items],
  );
  const key = built?.ok ? `${inputKey(built.body)}#${attempt}` : null;

  useEffect(() => {
    if (!client || !built?.ok || !key) return;
    const k = inputKey(built.body);
    if (resultCache.get(k)) return;
    let live = true;
    client.evaluate(built.body).then((r) => {
      if (!live) return;
      if (r.ok) {
        resultCache.set(k, r.data);
        resultCache.markEvaluated(k);
      }
      setAnswer({ key, error: r.ok ? null : r.error });
    });
    return () => {
      live = false;
    };
  }, [client, built, key]);

  if (!ready || !client || !built) return { status: "idle", retry };
  if (!built.ok) return { status: "blocked", reason: built.reason, retry };
  const k = inputKey(built.body);
  const cached = resultCache.get<CascadeResult>(k);
  if (cached) {
    resultCache.markEvaluated(k);
    return { status: "ok", result: cached, input: built.body, retry };
  }
  if (answer && answer.key === key && answer.error)
    return { status: "error", error: answer.error, retry };
  return { status: "loading", retry };
}

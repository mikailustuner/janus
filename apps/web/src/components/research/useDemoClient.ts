"use client";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { useDemo } from "@/demo/session";

const noSubscribe = () => () => {};

/**
 * The live client, or the demo client once the recorded fixture is loaded (experience Req 4.4).
 * Nothing is chosen before the first client render, so a live request never leaves in demo mode.
 * `live`, `load` and `demo` must be module-level values (stable across renders).
 */
export function useDemoClient<F extends { recorded: string }, C>(
  live: C,
  load: () => Promise<F>,
  demo: (fx: F) => C,
): { client: C | null; recorded: string | null; failed: boolean } {
  const isDemo = useDemo();
  const mounted = useSyncExternalStore(
    noSubscribe,
    () => true,
    () => false,
  );
  const [fx, setFx] = useState<F | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let on = true;
    if (isDemo)
      load().then(
        (f) => on && setFx(f),
        () => on && setFailed(true),
      );
    return () => {
      on = false;
    };
  }, [isDemo, load]);
  const client = useMemo(
    () => (!mounted ? null : isDemo ? (fx ? demo(fx) : null) : live),
    [mounted, isDemo, fx, live, demo],
  );
  return {
    client,
    recorded: isDemo ? (fx?.recorded ?? null) : null,
    failed: !!isDemo && failed,
  };
}

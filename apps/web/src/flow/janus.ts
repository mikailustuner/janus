"use client";
/**
 * Which client answers, and which list is current (experience design §4.1, DP11, DP29): in demo
 * mode the fixture client and the demo patient's items (read-only, never the person's list);
 * otherwise the HTTP client and the stored list. Medical results are kept in memory only.
 */
import { useEffect, useMemo, useState } from "react";

import {
  HttpClient,
  type JanusClient,
  type JanusReadClient,
} from "@/api/client";
import {
  DemoClient,
  demoItems,
  loadFixture,
  type Fixture,
} from "@/demo/client";
import { useDemo, type PatientId } from "@/demo/session";
import { useList } from "@/store/hooks";
import type { Item } from "@/store/list";

const http = new HttpClient();

export interface Session {
  ready: boolean;
  demo: PatientId | null;
  fixture: Fixture | null;
  client: JanusReadClient | null;
  /** The write and loop routes: null in demo mode (P14). */
  loop: JanusClient | null;
  items: Item[];
  readOnly: boolean;
}

export function useSession(): Session {
  const demo = useDemo();
  const list = useList();
  const [fixture, setFixture] = useState<Fixture | null>(null);
  useEffect(() => {
    let live = true;
    if (demo) loadFixture(demo).then((f) => live && setFixture(f));
    return () => {
      live = false;
    };
  }, [demo]);
  const f = demo && fixture && fixture.patient === demo ? fixture : null;
  const demoParts = useMemo(
    () => (f ? { client: new DemoClient(f), items: demoItems(f) } : null),
    [f],
  );
  if (demo) {
    return {
      ready: demoParts !== null,
      demo,
      fixture: f,
      client: demoParts?.client ?? null,
      loop: null,
      items: demoParts?.items ?? [],
      readOnly: true,
    };
  }
  return {
    ready: list.ready,
    demo: null,
    fixture: null,
    // No client until the store is read: during hydration demo mode is not known yet (C4).
    client: list.ready ? http : null,
    loop: list.ready ? http : null,
    items: list.value.items,
    readOnly: false,
  };
}

/** In-memory results by evaluation input (DP29): never persisted, gone on reload. */
const results = new Map<string, unknown>();
let lastEvaluation: string | null = null;
export const resultCache = {
  get: <T>(key: string) => results.get(key) as T | undefined,
  set: (key: string, value: unknown) => void results.set(key, value),
  clear: () => {
    results.clear();
    lastEvaluation = null;
  },
  /** The input key of the last successful evaluation; another current key means "out of date". */
  get last() {
    return lastEvaluation;
  },
  markEvaluated: (key: string) => {
    lastEvaluation = key;
  },
};

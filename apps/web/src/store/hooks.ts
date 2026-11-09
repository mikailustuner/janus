"use client";
/**
 * React bindings of the store (useSyncExternalStore; no state library, design §4.1). On the
 * server and during hydration `ready` is false, so screens render their loading state instead of
 * an empty list (no hydration mismatch, no flash of empty content).
 */
import { useCallback, useSyncExternalStore } from "react";

import { entriesDoc } from "@/passport/entries";

import { list, type ListDoc } from "./list";
import { DEFAULT_SETTINGS, settings, type Settings } from "./settings";
import { PREFIX, storage, type Doc, type Notice } from "./storage";
import { tokens } from "./tokens";
import { zombie } from "./zombie";

const noop = () => () => {};

function useDoc<T>(doc: Doc<T>, fallback: T): { ready: boolean; value: T } {
  const value = useSyncExternalStore(
    doc.subscribe,
    doc.getSnapshot,
    () => fallback,
  );
  const ready = useSyncExternalStore(
    noop,
    () => true,
    () => false,
  );
  return { ready, value: ready ? value : fallback };
}

const EMPTY_LIST: ListDoc = { v: 1, items: [] };

export const useSettings = () => useDoc<Settings>(settings, DEFAULT_SETTINGS);
export const useList = () => useDoc<ListDoc>(list, EMPTY_LIST);

export function updateSettings(patch: Partial<Omit<Settings, "v">>): void {
  settings.update((s) => ({ ...s, ...patch }));
  if (typeof document === "undefined") return;
  const s = settings.get();
  const root = document.documentElement;
  root.dataset.themeStyle = s.theme;
  root.dataset.largeText = s.largeText ? "on" : "off";
  root.dataset.reduceTransparency = s.reduceTransparency ? "on" : "off";
}

const NO_NOTICES: ReadonlySet<Notice> = new Set<Notice>();

/** The storage notices raised this session (shown once each, Req 9.4, 9.5). */
export function useStorageNotices(): ReadonlySet<Notice> {
  const subscribe = useCallback((l: () => void) => storage.onNotice(l), []);
  const raised = useSyncExternalStore(
    subscribe,
    () => storage.raised.size,
    () => 0,
  );
  return raised === 0 ? NO_NOTICES : new Set(storage.raised);
}

/**
 * "Delete everything on this device" (Req 9.6): every Janus key of local and session storage and
 * every Janus cache of the service worker. Donated data and doctor outcomes are not touched (they
 * are deleted only with their tokens).
 */
export async function deleteEverything(): Promise<void> {
  for (const key of storage.keys()) storage.remove(key);
  try {
    for (let i = sessionStorage.length - 1; i >= 0; i--) {
      const k = sessionStorage.key(i);
      if (k?.startsWith("janus.")) sessionStorage.removeItem(k);
    }
  } catch {
    /* session storage blocked: nothing kept there */
  }
  try {
    if (typeof caches !== "undefined")
      for (const name of await caches.keys())
        if (name.startsWith("janus")) await caches.delete(name);
  } catch {
    /* no cache storage */
  }
  for (const doc of [
    settings,
    list,
    tokens,
    entriesDoc,
    zombie,
  ] as Doc<unknown>[])
    doc.reset();
  updateSettings({});
}

export { PREFIX };

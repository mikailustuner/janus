"use client";
/**
 * The Passport's list (design §6, §9): in demo mode the demo patient's boxes (Cologne: the
 * Passport demo list; the others: their fixture items), otherwise the person's stored list; one
 * item per box, merged by identity, with the strength and form typed from the box applied. The
 * presence answer is kept in memory only, keyed by the request bodies (never persisted).
 */
import { useEffect, useMemo, useState } from "react";

import { keyName } from "@/components/names";
import { COLOGNE_PASSPORT, RECORDED } from "@/demo/passport-cologne";
import { useSession } from "@/flow/janus";
import { useVocabulary } from "@/vocabulary/use";

import { livePresence, loadPresence, type PresenceState } from "../client";
import { useEntries, withEntry } from "../entries";
import { itemIdentity } from "../identity";
import { mergeLists } from "../merge";
import { fromListItem, type PassportItem } from "../model";
import { buildPresenceRequests } from "../request";

export interface PassportView {
  ready: boolean;
  demo: string | null;
  readOnly: boolean;
  items: PassportItem[];
  /** list item id → id of the merged Passport item it became (same box added twice). */
  resolveId: (id: string) => string | undefined;
}

export function usePassport(): PassportView {
  const session = useSession();
  const vocab = useVocabulary();
  const demo = session.demo;
  const entries = useEntries();
  const { items, aliases } = useMemo(() => {
    if (!session.ready || !vocab)
      return { items: [], aliases: new Map<string, string>() };
    const base =
      demo === "cologne"
        ? COLOGNE_PASSPORT
        : session.items.map((i) =>
            fromListItem(i, (_k, p) => p, demo !== null),
          );
    const prepared = base.map((item) =>
      withEntry(
        {
          ...item,
          ingredients: item.ingredients.map((g) => ({
            ...g,
            label: g.key ? keyName(vocab, g.key, g.label || null) : g.label,
          })),
        },
        demo ? undefined : entries.entries[item.id],
      ),
    );
    const merged = mergeLists(prepared, []);
    const byIdentity = new Map(merged.map((m) => [itemIdentity(m), m.id]));
    return {
      items: merged,
      aliases: new Map(
        prepared.map((p) => [p.id, byIdentity.get(itemIdentity(p))!]),
      ),
    };
  }, [session.ready, session.items, vocab, demo, entries]);
  return {
    ready: session.ready && !!vocab,
    demo,
    readOnly: session.readOnly,
    items,
    resolveId: (id) => aliases.get(id),
  };
}

const cache = new Map<string, PresenceState>();

export type PresenceView = { status: "loading" } | PresenceState;

/** The presence answer for the list, with a retry. One call for the whole list (DP1). */
export function usePresence(
  items: readonly PassportItem[],
  ready: boolean,
  demo: string | null,
): PresenceView & { retry: () => void } {
  const key = useMemo(
    () => JSON.stringify(buildPresenceRequests(items).bodies),
    [items],
  );
  const [state, setState] = useState<{
    key: string;
    value: PresenceState;
  } | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!ready || cache.has(key)) return;
    let live = true;
    loadPresence(
      items,
      demo ? null : livePresence,
      demo ? (RECORDED[demo] ?? null) : null,
    ).then((value) => {
      if (value.status === "ok") cache.set(key, value);
      if (live) setState({ key, value });
    });
    return () => {
      live = false;
    };
    // `items` is captured through `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ready, demo, n]);
  const retry = () => {
    setState(null);
    setN((x) => x + 1);
  };
  const cached = cache.get(key);
  if (cached) return { ...cached, retry };
  if (state && state.key === key) return { ...state.value, retry };
  return { status: "loading", retry };
}

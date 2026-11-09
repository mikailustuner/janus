"use client";
/**
 * Zombie Alert in the browser (zombie-alert design §4): the check, the notification, and the
 * actions of the alert and the note screen. Live state is `janus.v1.zombie`; the demo uses a
 * memory-only document and never reaches the network (Req 6.1).
 */
import { useSyncExternalStore } from "react";

import type { JanusChangesClient, JanusReadClient } from "@/api/client";
import type { NoteOut } from "@/api/contracts";
import { useDemo } from "@/demo/session";
import { DEMO_CHANGE, DEMO_NOTICE } from "@/demo/zombie";
import { localDate } from "@/store/reminders";
import type { Doc } from "@/store/storage";
import { demoZombie, zombie } from "@/store/zombie";

import {
  changeKey,
  checkBody,
  diffNote,
  EMPTY,
  matchChanges,
  nextSince,
  noticesFrom,
  watchNote,
  withoutEvidence,
  type Alert,
  type ZombieDoc,
} from "./zombie";

export const docFor = (demo: boolean): Doc<ZombieDoc> =>
  demo ? demoZombie : zombie;

const noop = () => () => {};

/** The current document (the demo's in demo mode); `ready` is false on the server. */
export function useZombie(): { ready: boolean; demo: boolean; doc: ZombieDoc } {
  const demo = !!useDemo();
  const d = docFor(demo);
  const doc = useSyncExternalStore(d.subscribe, d.getSnapshot, () => EMPTY);
  const ready = useSyncExternalStore(
    noop,
    () => true,
    () => false,
  );
  return { ready, demo, doc: ready ? doc : EMPTY };
}

/** The opt-in; in demo mode it lives in the demo's memory document (Req 6.1). */
export function useNotifyOptIn(): boolean {
  const d = docFor(!!useDemo());
  return useSyncExternalStore(
    d.subscribe,
    () => d.get().notify,
    () => false,
  );
}

let inflight: Promise<Alert[]> | null = null;

/**
 * One check (Req 2.3–2.6, DP1): `since` and `limit` only, never an id. A failure changes nothing
 * but the attempt time. Single flight.
 */
export function runCheck(
  client: JanusChangesClient,
  d: Doc<ZombieDoc> = zombie,
  now: number = Date.now(),
): Promise<Alert[]> {
  if (inflight) return inflight;
  const body = checkBody(d.get());
  if (!body) return Promise.resolve([]);
  d.update((z) => ({ ...z, checkedAt: now }));
  inflight = (async () => {
    const r = await client.evidenceChanges(body);
    if (!r.ok) return [];
    const cur = d.get();
    const m = matchChanges(cur, r.data.changes);
    d.set({
      ...cur,
      since: nextSince(r.data),
      seen: m.seen,
      alerts: [...cur.alerts, ...m.alerts],
    });
    return m.alerts;
  })().finally(() => {
    inflight = null;
  });
  return inflight;
}

/** One local notification, through the service worker when registered (Req 4.3, 4.4, DP5). */
export async function notify(text: string, url: string): Promise<boolean> {
  if (
    typeof Notification === "undefined" ||
    Notification.permission !== "granted"
  )
    return false;
  const options: NotificationOptions = {
    body: text,
    tag: "janus-source-update",
    icon: "/icon.svg",
    data: { url },
  };
  try {
    const reg = await navigator.serviceWorker?.getRegistration();
    if (reg) {
      await reg.showNotification("Janus", options);
      return true;
    }
  } catch {
    /* fall back to the page notification */
  }
  try {
    const n = new Notification("Janus", options);
    n.onclick = () => {
      window.focus();
      location.assign(url);
    };
    return true;
  } catch {
    return false;
  }
}

/** Asks the permission in the tap that turns the switch on (Req 4.2). */
export async function setNotify(
  on: boolean,
  demo: boolean,
): Promise<"on" | "off" | "denied" | "unsupported"> {
  const zombie = docFor(demo);
  if (!on) {
    zombie.update((z) => ({ ...z, notify: false }));
    return "off";
  }
  if (typeof Notification === "undefined") return "unsupported";
  let p: NotificationPermission = Notification.permission;
  try {
    if (p === "default") p = await Notification.requestPermission();
  } catch {
    return "unsupported";
  }
  if (p !== "granted") {
    zombie.update((z) => ({ ...z, notify: false }));
    return "denied";
  }
  zombie.update((z) => ({ ...z, notify: true }));
  return "on";
}

/**
 * A note was received (Req 1.1, 5.2, 5.3): an open alert whose source the new note no longer
 * cites becomes "What changed"; the new note's ids replace the stored ones.
 */
export function recordNote(note: NoteOut, demo: boolean): void {
  const d = docFor(demo);
  const cur = d.get();
  const next = watchNote(note, localDate());
  const resolved = cur.alerts.filter((a) => !next.ids.includes(a.evidenceId));
  const open = cur.alerts.filter((a) => next.ids.includes(a.evidenceId));
  d.set({
    ...cur,
    note: next,
    alerts: open,
    update:
      resolved.length && cur.note
        ? {
            alerts: resolved,
            language: cur.note.language,
            ...diffNote(
              cur.note.sentences,
              note,
              resolved.map((a) => a.evidenceId),
            ),
          }
        : cur.update,
  });
}

/** The demo's note after the simulated retraction (Req 6.4, DP10); unchanged otherwise. */
export function demoAdjust(note: NoteOut, demo: boolean): NoteOut {
  return demo && demoZombie.get().seen.includes(changeKey(DEMO_CHANGE))
    ? withoutEvidence(note, [DEMO_CHANGE.evidence_id])
    : note;
}

/** True when the demo note cites the simulated source and it was not simulated yet. */
export const canSimulate = (doc: ZombieDoc) =>
  !!doc.note?.ids.includes(DEMO_CHANGE.evidence_id) &&
  !doc.seen.includes(changeKey(DEMO_CHANGE));

/** "Simulate a source retraction (demo)" (Req 6.2): the same match as a live check. */
export function simulate(): Alert[] {
  const cur = demoZombie.get();
  const m = matchChanges(cur, [DEMO_CHANGE], true, {
    [DEMO_CHANGE.evidence_id]: DEMO_NOTICE,
  });
  demoZombie.set({
    ...cur,
    seen: m.seen,
    alerts: [...cur.alerts, ...m.alerts],
  });
  return m.alerts;
}

/** The retraction notices of the open alerts, from resolve with their ids only (DP2). */
export async function fillNotices(
  client: Pick<JanusReadClient, "resolveEvidence">,
  demo: boolean,
): Promise<void> {
  if (demo) return;
  const ids = zombie
    .get()
    .alerts.filter((a) => !a.notice)
    .map((a) => a.evidenceId);
  if (!ids.length) return;
  const r = await client.resolveEvidence({ evidence_ids: [...new Set(ids)] });
  if (!r.ok) return;
  const notices = noticesFrom(r.data);
  zombie.update((z) => ({
    ...z,
    alerts: z.alerts.map((a) =>
      a.notice ? a : { ...a, notice: notices[a.evidenceId] ?? null },
    ),
  }));
}

export const dismissAlerts = (demo: boolean) =>
  docFor(demo).update((z) => ({ ...z, alerts: [] }));
export const dismissUpdate = (demo: boolean) =>
  docFor(demo).update((z) => ({ ...z, update: null }));

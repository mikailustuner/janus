/**
 * The Zombie Alert document `janus.v1.zombie` (zombie-alert design §3.1, Req 1). Browser only;
 * validated on read (an invalid shape gives the empty document, P6). The demo has its own
 * memory-only document, so demo mode writes nothing to local storage (Req 6.1).
 */
import {
  EMPTY,
  type Alert,
  type KeptSentence,
  type Update,
  type WatchedNote,
  type ZombieDoc,
} from "@/flow/zombie";

import { Doc, PREFIX, SafeStorage, storage } from "./storage";

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const isStr = (v: unknown): v is string => typeof v === "string";
const isStrs = (v: unknown): v is string[] =>
  Array.isArray(v) && v.every(isStr);
const isObj = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const nullOr = <T>(v: unknown, f: (x: unknown) => x is T): v is T | null =>
  v === null || f(v);

function sentence(v: unknown): v is KeptSentence {
  return isObj(v) && isStr(v.id) && isStr(v.text) && isStrs(v.ids);
}

function note(v: unknown): v is WatchedNote {
  return (
    isObj(v) &&
    isStr(v.language) &&
    isStr(v.madeOn) &&
    DATE.test(v.madeOn) &&
    isStrs(v.ids) &&
    Array.isArray(v.sentences) &&
    v.sentences.every(sentence)
  );
}

function alert(v: unknown): v is Alert {
  return (
    isObj(v) &&
    isStr(v.key) &&
    isStr(v.evidenceId) &&
    nullOr(v.title, isStr) &&
    nullOr(v.doi, isStr) &&
    isStr(v.observedOn) &&
    typeof v.simulated === "boolean" &&
    (v.notice === null ||
      (isObj(v.notice) &&
        nullOr(v.notice.doi, isStr) &&
        nullOr(v.notice.url, isStr)))
  );
}

function update(v: unknown): v is Update {
  return (
    isObj(v) &&
    isStr(v.language) &&
    Array.isArray(v.alerts) &&
    v.alerts.every(alert) &&
    Array.isArray(v.removed) &&
    v.removed.every(sentence) &&
    Array.isArray(v.changed) &&
    v.changed.every((c) => isObj(c) && sentence(c.before) && sentence(c.after))
  );
}

export function validateZombie(v: unknown): ZombieDoc | null {
  if (!isObj(v) || v.v !== 1) return null;
  if (
    typeof v.notify !== "boolean" ||
    !nullOr(v.note, note) ||
    !nullOr(v.since, (x): x is string => isStr(x) && DATE.test(x)) ||
    !(v.checkedAt === null || Number.isFinite(v.checkedAt)) ||
    !isStrs(v.seen) ||
    !Array.isArray(v.alerts) ||
    !v.alerts.every(alert) ||
    !nullOr(v.update, update)
  )
    return null;
  return {
    v: 1,
    notify: v.notify,
    note: v.note,
    since: v.since,
    checkedAt: v.checkedAt as number | null,
    seen: v.seen,
    alerts: v.alerts,
    update: v.update,
  };
}

export function zombieDoc(store: SafeStorage = storage) {
  return new Doc<ZombieDoc>(store, `${PREFIX}zombie`, validateZombie, () => ({
    ...EMPTY,
  }));
}

/** The person's document (local storage, SafeStorage fallback). */
export const zombie = zombieDoc();

/** The demo's document: memory only, gone with the page (Req 6.1). */
export const demoZombie = zombieDoc(new SafeStorage(() => null));

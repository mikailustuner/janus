"use client";
/**
 * Strength and form typed from the box (DP21, owner decision 1), per list item id. Kept in the
 * browser only (`janus.v1.passport`, removed by "delete everything"); the demo lists are read-only
 * and have none. Applied to a Passport item as values with origin `entered`.
 */
import { useSyncExternalStore } from "react";

import { Doc, PREFIX, storage } from "@/store/storage";

import {
  AMOUNT,
  BASES,
  FORM_GROUPS,
  UNITS,
  type FormGroup,
  type PassportItem,
  type StrengthCode,
} from "./model";

export interface Entry {
  strengths: Record<string, StrengthCode>;
  form: FormGroup | null;
}
export interface EntriesDoc {
  v: 1;
  entries: Record<string, Entry>;
}

const isCode = (v: unknown): v is StrengthCode => {
  const o = v as Record<string, unknown> | null;
  return (
    !!o &&
    typeof o.amount === "string" &&
    AMOUNT.test(o.amount) &&
    (UNITS as readonly unknown[]).includes(o.unit) &&
    (BASES as readonly unknown[]).includes(o.basis)
  );
};

export function validateEntries(v: unknown): EntriesDoc | null {
  const o = v as Record<string, unknown> | null;
  if (!o || o.v !== 1 || typeof o.entries !== "object" || !o.entries)
    return null;
  const entries: Record<string, Entry> = {};
  for (const [id, raw] of Object.entries(
    o.entries as Record<string, unknown>,
  )) {
    const e = raw as Record<string, unknown> | null;
    if (!e || typeof e.strengths !== "object" || !e.strengths) return null;
    const strengths: Record<string, StrengthCode> = {};
    for (const [k, s] of Object.entries(
      e.strengths as Record<string, unknown>,
    )) {
      if (!isCode(s)) return null;
      strengths[k] = { amount: s.amount, unit: s.unit, basis: s.basis };
    }
    const form = e.form ?? null;
    if (form !== null && !(FORM_GROUPS as readonly unknown[]).includes(form))
      return null;
    entries[id] = { strengths, form: form as FormGroup | null };
  }
  return { v: 1, entries };
}

const EMPTY: EntriesDoc = { v: 1, entries: {} };
export const entriesDoc = new Doc<EntriesDoc>(
  storage,
  `${PREFIX}passport`,
  validateEntries,
  () => EMPTY,
);

export function setEntry(id: string, entry: Entry | null): void {
  entriesDoc.update((d) => {
    const entries = { ...d.entries };
    if (entry) entries[id] = entry;
    else delete entries[id];
    return { v: 1, entries };
  });
}

export function useEntries(): EntriesDoc {
  return useSyncExternalStore(
    entriesDoc.subscribe,
    entriesDoc.getSnapshot,
    () => EMPTY,
  );
}

/** The item with its typed values; values from the source are never overwritten. */
export function withEntry(
  item: PassportItem,
  entry: Entry | undefined,
): PassportItem {
  if (!entry) return item;
  return {
    ...item,
    ingredients: item.ingredients.map((i) => {
      const typed = i.key ? entry.strengths[i.key] : undefined;
      return typed && i.strengthOrigin !== "source"
        ? { ...i, strength: typed, strengthOrigin: "entered" }
        : i;
    }),
    doseForm:
      item.doseForm?.origin !== "source" && entry.form
        ? { group: entry.form, origin: "entered" }
        : item.doseForm,
  };
}

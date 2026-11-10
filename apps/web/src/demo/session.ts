"use client";
/**
 * The demo session (experience design §4.1, §13, DP11). Held in memory; the chosen patient id is
 * mirrored to sessionStorage (`janus.v1.demo`, the id only) so a reload stays in the demo (DP33).
 * The demo never reads or writes the person's `list` or `tokens` (P14).
 */
import { useSyncExternalStore } from "react";

import { dispatchLabel } from "@/scan/label-session";

export const PATIENTS = ["istanbul", "cologne", "ohio"] as const;
export type PatientId = (typeof PATIENTS)[number];

const KEY = "janus.v1.demo";
let current: PatientId | null | undefined;
const listeners = new Set<() => void>();

function readSession(): PatientId | null {
  try {
    const v = sessionStorage.getItem(KEY);
    return (PATIENTS as readonly string[]).includes(v ?? "")
      ? (v as PatientId)
      : null;
  } catch {
    return null;
  }
}

export function demoPatient(): PatientId | null {
  if (current === undefined)
    current = typeof window === "undefined" ? null : readSession();
  return current;
}

export function startDemo(patient: PatientId): void {
  current = patient;
  // A label of the user's own box is not shown inside the demo.
  dispatchLabel({ type: "clear" });
  try {
    sessionStorage.setItem(KEY, patient);
  } catch {
    /* kept in memory only */
  }
  for (const l of listeners) l();
}

export function exitDemo(): void {
  current = null;
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* nothing kept */
  }
  for (const l of listeners) l();
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

/** The active demo patient, or null outside demo mode (null on the server). */
export function useDemo(): PatientId | null {
  return useSyncExternalStore(subscribe, demoPatient, () => null);
}

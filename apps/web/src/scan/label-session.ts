"use client";
/**
 * The result of the last label photo (ocr-first design §5, Req 2, P5). The photo is dropped as
 * soon as it has been read; the recognised words and the ingredient candidates stay in memory,
 * so a label that names several ingredients can be added one after the other, until the next
 * photo, "remove", or the tab closes. Never stored, never sent.
 *
 * `outboundOf` is the only way from a result to a request: it needs a choice made by the user.
 * No state holds a chosen candidate, so nothing can be confirmed without one.
 */
import { useSyncExternalStore } from "react";

import type { IngredientCandidate } from "./ingredient-match";
import { ndcCandidates, selectionQuery } from "./ocr-extract";
import type { Pass } from "./ocr-passes";

export interface LabelResult {
  candidates: IngredientCandidate[];
  ndcs: string[];
  words: string[];
}

export type LabelState =
  | { kind: "idle" }
  | { kind: "busy"; progress: number; turned: boolean }
  | { kind: "failed" }
  | { kind: "none" }
  | { kind: "done"; result: LabelResult };

export type LabelAction =
  | { type: "start" }
  | { type: "progress"; progress: number; turned: boolean }
  | { type: "read"; result: LabelResult }
  | { type: "failed" }
  | { type: "clear" };

export type Choice =
  | { kind: "ingredient"; index: number }
  | { kind: "ndc"; index: number }
  | { kind: "words"; selected: readonly number[] };

export type Outbound =
  /** `key` is set when the query is the name of an ingredient the user chose. */
  | { kind: "search"; query: string; key: string | null }
  | { kind: "ndc"; ndc: string };

export function labelResult(
  pass: Pass,
  match: (lines: string[]) => IngredientCandidate[],
): LabelResult {
  const lines = pass.lines.map((l) => l.text);
  return {
    candidates: match(lines),
    ndcs: ndcCandidates(lines.join("\n")),
    words: pass.lines.flatMap((l) => l.words),
  };
}

export function reduce(state: LabelState, action: LabelAction): LabelState {
  switch (action.type) {
    case "start":
      return { kind: "busy", progress: 0, turned: false };
    case "progress":
      return state.kind === "busy"
        ? { kind: "busy", progress: action.progress, turned: action.turned }
        : state;
    case "read":
      if (state.kind !== "busy") return state;
      return action.result.words.length > 0
        ? { kind: "done", result: action.result }
        : { kind: "none" };
    case "failed":
      return state.kind === "busy" ? { kind: "failed" } : state;
    case "clear":
      return { kind: "idle" };
  }
}

/**
 * What a choice of the user sends: the English name of the chosen ingredient, the chosen NDC, or
 * exactly the chosen adjacent words. Null for anything that is not a valid choice in a result.
 */
export function outboundOf(
  state: LabelState,
  choice: Choice,
  englishNames: Readonly<Record<string, string>>,
): Outbound | null {
  if (state.kind !== "done") return null;
  const { result } = state;
  if (choice.kind === "ingredient") {
    const c = Number.isInteger(choice.index)
      ? result.candidates[choice.index]
      : undefined;
    const name = c && Object.hasOwn(englishNames, c.key) && englishNames[c.key];
    return c && name ? { kind: "search", query: name, key: c.key } : null;
  }
  if (choice.kind === "ndc") {
    const ndc = Number.isInteger(choice.index)
      ? result.ndcs[choice.index]
      : undefined;
    return ndc ? { kind: "ndc", ndc } : null;
  }
  const query = selectionQuery(result.words, choice.selected);
  return query ? { kind: "search", query, key: null } : null;
}

let current: LabelState = { kind: "idle" };
const listeners = new Set<() => void>();

export function dispatchLabel(action: LabelAction) {
  current = reduce(current, action);
  for (const l of listeners) l();
}

/** The current state, for code outside React. */
export const labelState = (): LabelState => current;

export function useLabelState(): LabelState {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => current,
    () => IDLE,
  );
}

const IDLE: LabelState = { kind: "idle" };

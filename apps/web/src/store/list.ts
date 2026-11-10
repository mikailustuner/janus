/**
 * The medicine list `janus.v1.list` (experience design §4.1, §15, Req 9.3, 13.2, 26.1). Lives only
 * in the browser. `candidate` is kept as returned for display and carries what the Passport needs
 * (region, country, source and date, ingredient keys with ATC codes).
 */
import type { Candidate, ScanRegion } from "@/api/contracts";
import { candidate as candidateDecoder, decode } from "@/api/decode";
import { usableLot } from "@/recall/lot";

import { Doc, PREFIX, storage, type SafeStorage } from "./storage";

export type SourceKey =
  | { kind: "scan"; content: string }
  | { kind: "ndc"; ndc: string }
  | {
      kind: "search";
      query: string;
      region: ScanRegion | null;
      pick:
        | { kind: "product"; sourceId: string; productName: string | null }
        | { kind: "ingredient"; qid: string };
    };

export interface Choice {
  position: number;
  ingredient: string;
}

export interface Item {
  id: string;
  sourceKey: SourceKey;
  datasetVersion: string;
  candidate: Candidate;
  choices: Choice[];
  started: string | null; // "YYYY-MM"
  boxName: string;
  needsConfirmation: boolean;
  /** The lot of the scanned box, AI (10): never sent to a server (recall-check Req 5). */
  lot?: string;
}

export interface ListDoc {
  v: 1;
  items: Item[];
}

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
const HEX64 = /^[0-9a-f]{64}$/;

function validSourceKey(v: unknown): v is SourceKey {
  if (typeof v !== "object" || v === null) return false;
  const o = v as Record<string, unknown>;
  if (o.kind === "scan") return typeof o.content === "string";
  if (o.kind === "ndc") return typeof o.ndc === "string";
  if (o.kind !== "search" || typeof o.query !== "string") return false;
  if (!(
    o.region === null ||
    o.region === "TR" ||
    o.region === "US" ||
    o.region === "EU"
  ))
    return false;
  const p = o.pick as Record<string, unknown> | null;
  if (!p || typeof p !== "object") return false;
  if (p.kind === "ingredient") return typeof p.qid === "string";
  return (
    p.kind === "product" &&
    typeof p.sourceId === "string" &&
    (p.productName === null || typeof p.productName === "string")
  );
}

export function validateItem(v: unknown): Item | null {
  if (typeof v !== "object" || v === null) return null;
  const o = v as Record<string, unknown>;
  if (typeof o.id !== "string" || !validSourceKey(o.sourceKey)) return null;
  if (typeof o.datasetVersion !== "string" || !HEX64.test(o.datasetVersion))
    return null;
  const c = decode(candidateDecoder, o.candidate);
  if (!c.ok) return null;
  if (!Array.isArray(o.choices)) return null;
  const choices: Choice[] = [];
  for (const ch of o.choices) {
    const x = ch as Record<string, unknown> | null;
    if (!x || !Number.isInteger(x.position) || typeof x.ingredient !== "string")
      return null;
    choices.push({ position: x.position as number, ingredient: x.ingredient });
  }
  if (!(
    o.started === null ||
    (typeof o.started === "string" && MONTH.test(o.started))
  ))
    return null;
  if (typeof o.boxName !== "string" || typeof o.needsConfirmation !== "boolean")
    return null;
  if (o.lot !== undefined && (typeof o.lot !== "string" || !usableLot(o.lot)))
    return null;
  return {
    id: o.id,
    sourceKey: o.sourceKey,
    datasetVersion: o.datasetVersion,
    candidate: c.value,
    choices,
    started: o.started as string | null,
    boxName: o.boxName,
    needsConfirmation: o.needsConfirmation,
    ...(o.lot === undefined ? {} : { lot: o.lot }),
  };
}

export function validateList(v: unknown): ListDoc | null {
  if (typeof v !== "object" || v === null) return null;
  const o = v as Record<string, unknown>;
  if (o.v !== 1 || !Array.isArray(o.items)) return null;
  const items: Item[] = [];
  for (const raw of o.items) {
    const item = validateItem(raw);
    if (!item) return null;
    items.push(item);
  }
  return { v: 1, items };
}

export function listDoc(store: SafeStorage = storage) {
  return new Doc<ListDoc>(store, `${PREFIX}list`, validateList, () => ({
    v: 1,
    items: [],
  }));
}

export const list = listDoc();

const newId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `i-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

/** Item actions (Req 13.2). Each replaces the document, which marks results out of date. */
export const listActions = (doc = list) => ({
  add(item: Omit<Item, "id">): string {
    const id = newId();
    doc.update((l) => ({ ...l, items: [...l.items, { ...item, id }] }));
    return id;
  },
  edit(
    id: string,
    patch: Partial<Pick<Item, "started" | "boxName" | "choices">>,
  ): void {
    doc.update((l) => ({
      ...l,
      items: l.items.map((i) => (i.id === id ? { ...i, ...patch } : i)),
    }));
  },
  /** Confirm an item again (after a dataset change): new candidate, same place in the list. */
  replace(id: string, item: Omit<Item, "id">): void {
    doc.update((l) => ({
      ...l,
      items: l.items.map((i) => (i.id === id ? { ...item, id } : i)),
    }));
  },
  remove(id: string): void {
    doc.update((l) => ({ ...l, items: l.items.filter((i) => i.id !== id) }));
  },
});

/** Distinct ingredient keys of a list, sorted (§15; order and duplicates change nothing). */
export function listIngredientKeys(
  items: readonly Pick<Item, "candidate" | "choices">[],
): string[] {
  const keys = new Set<string>();
  for (const item of items) {
    const c = item.candidate;
    if (c.kind === "ingredient") keys.add(c.ingredient_key.qid);
    else
      for (const ing of c.ingredients) {
        if (ing.status === "mapped" && ing.ingredient_key)
          keys.add(ing.ingredient_key.qid);
        else if (ing.status === "ambiguous") {
          const chosen = item.choices.find(
            (ch) => ch.position === ing.position,
          );
          if (chosen) keys.add(chosen.ingredient);
        }
      }
  }
  return [...keys].sort();
}

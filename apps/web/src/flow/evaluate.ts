/**
 * List → `POST /cascades/evaluate` input (experience design §4, §5.4, Req 1.6, 13.1, 14.1, P3).
 * Keeps list order (evaluation index i is list item i), one kind per item, choices only for
 * ambiguous positions of a product, start months not after the current month, one dataset
 * version. Never an ATC code, never a box name.
 */
import { evaluateBody, itemIn } from "@/api/builders";
import type { EvaluateIn } from "@/api/contracts";
import type { Item } from "@/store/list";

export const MAX_ITEMS = 50;

export type EvaluateInput =
  | { ok: true; body: EvaluateIn }
  | {
      ok: false;
      reason:
        | "empty"
        | "too_many"
        | "mixed_versions"
        | "needs_confirmation"
        | "future_start";
    };

export function currentMonth(now: Date = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function toEvaluateIn(
  items: readonly Item[],
  now: Date = new Date(),
): EvaluateInput {
  if (items.length === 0) return { ok: false, reason: "empty" };
  if (items.length > MAX_ITEMS) return { ok: false, reason: "too_many" };
  if (items.some((i) => i.needsConfirmation))
    return { ok: false, reason: "needs_confirmation" };
  const versions = new Set(items.map((i) => i.datasetVersion));
  if (versions.size !== 1) return { ok: false, reason: "mixed_versions" };
  const month = currentMonth(now);
  if (items.some((i) => i.started !== null && i.started > month))
    return { ok: false, reason: "future_start" };
  const built = items.map((item) => {
    const c = item.candidate;
    if (c.kind === "ingredient")
      return itemIn({
        ingredient: c.ingredient_key.qid,
        started: item.started,
      });
    const ambiguous = new Set(
      c.ingredients
        .filter((g) => g.status === "ambiguous")
        .map((g) => g.position),
    );
    const choices = item.choices.filter(
      (ch) =>
        ambiguous.has(ch.position) &&
        c.ingredients
          .find((g) => g.position === ch.position)
          ?.key_candidates.includes(ch.ingredient),
    );
    return itemIn({ product: c.candidate_id, choices, started: item.started });
  });
  return { ok: true, body: evaluateBody([...versions][0]!, built) };
}

/** A stable key of an evaluation input, for the in-memory result cache (DP29). */
export function inputKey(body: EvaluateIn): string {
  return JSON.stringify(body);
}

/**
 * "Since when?" (Req 13.1): a month and year not later than the current month, or "don't know".
 * Returns the `started` value or an error code.
 */
export function monthInput(
  input: { dontKnow: true } | { dontKnow: false; year: number; month: number },
  now: Date = new Date(),
):
  | { ok: true; started: string | null }
  | { ok: false; reason: "future" | "invalid" } {
  if (input.dontKnow) return { ok: true, started: null };
  const { year, month } = input;
  if (
    !Number.isInteger(year) ||
    !Number.isInteger(month) ||
    month < 1 ||
    month > 12 ||
    year < 1900 ||
    year > 9999
  )
    return { ok: false, reason: "invalid" };
  const started = `${year}-${String(month).padStart(2, "0")}`;
  if (started > currentMonth(now)) return { ok: false, reason: "future" };
  return { ok: true, started };
}

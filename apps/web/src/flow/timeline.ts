/**
 * Timeline model (experience design §9, Req 13.3, P23): items with a start month in time order
 * (stable), items without one in their own lane, and each finding drawn once from its index
 * items to its marker items with the months between as the API returned them.
 */
import type { CascadeResult } from "@/api/contracts";
import type { Item } from "@/store/list";

export interface TimelineModel {
  dated: { item: number; started: string }[];
  undated: number[];
  links: {
    findingId: string;
    from: number[];
    to: number[];
    months: number | null;
    timing: string;
  }[];
  range: { first: string; last: string } | null;
}

export function timeline(
  items: readonly Pick<Item, "started">[],
  result: CascadeResult | null,
): TimelineModel {
  const dated = items
    .map((it, item) => ({ item, started: it.started }))
    .filter((x): x is { item: number; started: string } => x.started !== null)
    .sort((a, b) =>
      a.started < b.started ? -1 : a.started > b.started ? 1 : a.item - b.item,
    );
  const undated = items
    .map((it, i) => (it.started === null ? i : -1))
    .filter((i) => i >= 0);
  const links =
    result?.findings.map((f) => ({
      findingId: f.finding_id,
      from: [...f.index.items],
      to: [...f.marker.items],
      months: f.months_between,
      timing: f.timing,
    })) ?? [];
  const range = dated.length
    ? { first: dated[0]!.started, last: dated[dated.length - 1]!.started }
    : null;
  return { dated, undated, links, range };
}

/** Months from `a` to `b` ("YYYY-MM"), for placing a bar on the axis only (no medical meaning). */
export function monthIndex(month: string): number {
  const [y, m] = month.split("-").map(Number) as [number, number];
  return y * 12 + (m - 1);
}

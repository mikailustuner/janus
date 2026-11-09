/**
 * The Summary view model (janus-report design §3, DP3–DP7). Pure; computes no medical result: it
 * counts what `resultsView`, the list and the evidence resolutions already say. Every finding is in
 * exactly one timing group (P1); the warned items are the results screen's (P2).
 */
import type { CascadeResult, EvidenceResolution } from "@/api/contracts";
import type { Item } from "@/store/list";
import type { Loaded, SafetyLineCode } from "@/vocabulary";

import {
  ORDER_GROUPS,
  orderGroup,
  resultsView,
  type FindingView,
  type OrderGroup,
} from "./findings";
import { evidenceView } from "./integrity";

export const BOX_REGIONS = ["TR", "EU", "US", "name"] as const;
export type BoxRegion = (typeof BOX_REGIONS)[number];

export type SummaryView =
  | { kind: "unavailable" }
  | {
      kind: "ok";
      month: string;
      medicines: { total: number; notFully: number[] };
      patterns: {
        total: number;
        groups: Record<OrderGroup, FindingView[]>;
        unconfirmedForm: number;
      };
      /** All findings in API order (each once). */
      findings: FindingView[];
      noPattern: boolean;
      warnedItems: number[];
      safetyLines: SafetyLineCode[];
      emergencyFirst: boolean;
      rules: { checked: number; total: number };
      regions: Record<BoxRegion, number>;
      sources: { sourceId: string; date: string; items: number }[];
    };

export function boxRegion(item: Pick<Item, "candidate">): BoxRegion {
  return item.candidate.kind === "product" ? item.candidate.region : "name";
}

/**
 * Items with at least one ingredient that could not be checked ("partly checked"), in list order
 * (owner decision 2026-11-09, experience DP57, janus-report DP12).
 */
export function notFullyChecked(
  r: Pick<CascadeResult, "not_checked">,
  items: number,
): number[] {
  return [
    ...new Set(r.not_checked.map((n) => n.item).filter((i) => i < items)),
  ].sort((a, b) => a - b);
}

/** "8 medicines: 6 fully checked, 2 partly" (owner decision 2026-11-09). */
export function checkedSplit(
  r: Pick<CascadeResult, "not_checked">,
  items: number,
): { total: number; full: number; partly: number } {
  const partly = notFullyChecked(r, items).length;
  return { total: items, full: items - partly, partly };
}

export function summaryView(
  r: CascadeResult,
  items: readonly Pick<Item, "candidate">[],
  v: Loaded,
): SummaryView {
  const rv = resultsView(r, v);
  if (rv.kind === "unavailable") return rv;
  const findings = [...rv.confirmed, ...rv.unconfirmed].sort(
    (a, b) => a.position - b.position,
  );
  const groups = Object.fromEntries(
    ORDER_GROUPS.map((g) => [
      g,
      findings.filter((f) => orderGroup(f.finding.timing) === g),
    ]),
  ) as Record<OrderGroup, FindingView[]>;
  const notFully = notFullyChecked(r, items.length);
  const regions = Object.fromEntries(BOX_REGIONS.map((k) => [k, 0])) as Record<
    BoxRegion,
    number
  >;
  const sources = new Map<
    string,
    { sourceId: string; date: string; items: number }
  >();
  for (const it of items) {
    regions[boxRegion(it)] += 1;
    const src = it.candidate.source;
    const date = src.snapshot_date.slice(0, 10);
    const key = `${src.source_id}|${date}`;
    const row = sources.get(key) ?? { sourceId: src.source_id, date, items: 0 };
    row.items += 1;
    sources.set(key, row);
  }
  return {
    kind: "ok",
    month: r.as_of_month,
    medicines: { total: items.length, notFully },
    patterns: {
      total: findings.length,
      groups,
      unconfirmedForm: rv.unconfirmed.length,
    },
    findings,
    noPattern: rv.noPattern,
    warnedItems: rv.warnedItems.filter((i) => i < items.length),
    safetyLines: rv.safetyLines,
    emergencyFirst: rv.emergencyFirst,
    rules: rv.rules,
    regions,
    sources: [...sources.values()].sort(
      (a, b) =>
        a.sourceId.localeCompare(b.sourceId) || a.date.localeCompare(b.date),
    ),
  };
}

export interface IntegritySummary {
  /** Distinct evidence items used by the findings whose evidence loaded. */
  sources: number;
  /** True only when every loaded integrity line says no retracted source was used. */
  noRetracted: boolean;
  /** Findings whose integrity line lists an excluded source. */
  withExclusions: number;
  stale: { sourceId: string; date: string }[];
  /** Newest integrity check date over the lines, if any. */
  newestCheck: string | null;
}

export function integritySummary(
  resolutions: readonly EvidenceResolution[],
): IntegritySummary {
  const used = new Set<string>();
  const stale = new Map<string, string>();
  let newest: string | null = null;
  for (const r of resolutions) {
    for (const i of evidenceView(r).used) used.add(i.id);
    for (const s of r.line.stale_sources)
      if (!stale.has(s.source_id)) stale.set(s.source_id, s.snapshot_date);
    if (r.line.newest_check && (!newest || r.line.newest_check > newest))
      newest = r.line.newest_check;
  }
  return {
    sources: used.size,
    noRetracted:
      resolutions.length > 0 &&
      resolutions.every((r) => r.line.no_retracted_used),
    withExclusions: resolutions.filter((r) => r.line.excluded.length > 0)
      .length,
    stale: [...stale].map(([sourceId, date]) => ({ sourceId, date })),
    newestCheck: newest,
  };
}

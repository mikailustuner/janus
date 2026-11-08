/**
 * `CascadeResult` → the results view model (experience design §9, Req 1.3, 7, 14, P7, P9).
 * Pure; computes no medical result. It groups findings by `form_confirmed` in API order, keeps
 * `same_product` out of the findings, lists one abrupt-stop line per warned item, words every
 * not-checked entry and every disabled or not-matchable rule as "cannot be checked", and collects
 * the safety lines of the events shown (emergency notice first when there is any).
 */
import type { CascadeResult, Finding } from "@/api/contracts";
import { ruleRow, type Loaded, type SafetyLineCode } from "@/vocabulary";

import { eventKeyOf } from "./locator";

export interface FindingView {
  position: number;
  finding: Finding;
  eventKey: string | null;
  safetyLine: SafetyLineCode | null;
  /** Items of this finding that carry an abrupt-stop warning (each shown once on the card). */
  warnedItems: number[];
  supporting: boolean;
}

export type ResultsView =
  | { kind: "unavailable" }
  | {
      kind: "ok";
      confirmed: FindingView[];
      unconfirmed: FindingView[];
      unconfirmedCodes: string[];
      noPattern: boolean;
      warnedItems: number[];
      safetyLines: SafetyLineCode[];
      emergencyFirst: boolean;
      notChecked: { item: number; position: number; reason: string }[];
      rules: { checked: number; total: number };
      cannotCheck: {
        row: number;
        ruleId: string;
        reason: string;
        kind: "not_matchable" | "disabled";
      }[];
      chains: { chainId: string; keys: string[]; findingIds: string[] }[];
      chainsTruncated: boolean;
    };

const SUPPORTING = /^paper:thinkcascades:/;

export function resultsView(r: CascadeResult, v: Loaded): ResultsView {
  if (r.statement?.code === "rule_base_unavailable")
    return { kind: "unavailable" };
  const warned = [...new Set(r.item_warnings.map((w) => w.item))].sort(
    (a, b) => a - b,
  );
  const warnedSet = new Set(warned);
  const views: FindingView[] = r.findings.map((finding, position) => {
    const eventKey = eventKeyOf(finding, v);
    const items = [
      ...new Set([...finding.index.items, ...finding.marker.items]),
    ];
    return {
      position,
      finding,
      eventKey,
      safetyLine: eventKey
        ? (v.vocab.events[eventKey]?.safety_line ?? null)
        : null,
      warnedItems: items.filter((i) => warnedSet.has(i)),
      supporting: finding.evidence_ids.some((id) => SUPPORTING.test(id)),
    };
  });
  const confirmed = views.filter((f) => f.finding.form_confirmed);
  const unconfirmed = views.filter((f) => !f.finding.form_confirmed);
  const unconfirmedCodes = [
    ...new Set(
      unconfirmed.flatMap((f) => [
        ...(f.finding.index.form_confirmed
          ? []
          : f.finding.index.matched_codes),
        ...(f.finding.marker.form_confirmed
          ? []
          : f.finding.marker.matched_codes),
      ]),
    ),
  ];
  const safetyLines = [
    ...new Set(
      views.map((f) => f.safetyLine).filter((s): s is SafetyLineCode => !!s),
    ),
  ];
  const cannotCheck = [
    ...r.rules.not_matchable.map((n) => ({
      row: ruleRow(n.rule_id) ?? 0,
      ruleId: n.rule_id,
      reason: n.reason as string,
      kind: "not_matchable" as const,
    })),
    ...r.rules.disabled.map((d) => ({
      row: ruleRow(d.rule_id) ?? 0,
      ruleId: d.rule_id,
      reason: d.reason as string,
      kind: "disabled" as const,
    })),
  ];
  return {
    kind: "ok",
    confirmed,
    unconfirmed,
    unconfirmedCodes,
    noPattern:
      r.findings.length === 0 && r.statement?.code === "no_pattern_found",
    warnedItems: warned,
    safetyLines,
    emergencyFirst: safetyLines.length > 0,
    notChecked: r.not_checked.map((n) => ({ ...n })),
    rules: { checked: r.rules.checked, total: r.rules.total },
    cannotCheck,
    chains: r.chains.map((c) => ({
      chainId: c.chain_id,
      keys: c.ingredient_keys,
      findingIds: [...new Set(c.links.flatMap((l) => l.finding_ids))],
    })),
    chainsTruncated: r.notices.includes("chains_truncated"),
  };
}

/**
 * `EvidenceResolution` → the evidence view model (Req 15, P30). Retracted sources appear only
 * among the excluded sources (with the stamp or the "Retracted" label); the stamp never marks a
 * source the finding uses; "no retracted source used" iff `no_retracted_used`.
 */
import type { EvidenceItem, EvidenceResolution } from "@/api/contracts";

export interface EvidenceView {
  used: EvidenceItem[];
  excluded: {
    item: EvidenceItem | null;
    id: string;
    reason: string;
    stamp: boolean;
  }[];
  line: EvidenceResolution["line"];
  noRetracted: boolean;
  exceptions: { id: string; reason: string }[];
}

export function evidenceView(r: EvidenceResolution): EvidenceView {
  const byId = new Map(r.items.map((i) => [i.id, i]));
  const excludedIds = new Set([
    ...r.excluded.map((e) => e.id),
    ...r.items.filter((i) => i.exclusion_reason).map((i) => i.id),
  ]);
  const used = r.items.filter(
    (i) => !excludedIds.has(i.id) && i.integrity?.status !== "retracted",
  );
  const excludedList = [
    ...r.excluded,
    ...r.items
      .filter(
        (i) =>
          (i.exclusion_reason || i.integrity?.status === "retracted") &&
          !r.excluded.some((e) => e.id === i.id),
      )
      .map((i) => ({ id: i.id, reason: i.exclusion_reason ?? "retracted" })),
  ];
  return {
    used,
    excluded: excludedList.map((e) => ({
      id: e.id,
      reason: e.reason,
      item: byId.get(e.id) ?? null,
      stamp:
        e.reason === "retracted" ||
        byId.get(e.id)?.integrity?.status === "retracted",
    })),
    line: r.line,
    noRetracted: r.line.no_retracted_used,
    exceptions: r.line.excluded.map((e) => ({ ...e })),
  };
}

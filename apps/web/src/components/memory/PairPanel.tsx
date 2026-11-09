"use client";
/**
 * The FAERS pair panel of a finding detail (Req 16.1, 16.3–16.7, 29): the report count as a stat
 * tile (its sentence for screen readers), ratio with range and CI bar; the visible caveats right
 * under the numbers; the assessment only here, folded, with the screening sentence; limits, window,
 * attribution and the MedDRA notice when Preferred Terms are shown (PT names only in this view).
 */
import { useLocale } from "next-intl";

import type { PairOut, SnapshotOut } from "@/api/contracts";
import {
  Disclosure,
  StatGrid,
  StatTile,
  SummaryCard,
} from "@/components/cards";
import { formatCount, formatDate, formatShare } from "@/components/format";
import { pairPanel, splitCaveats } from "@/flow/memory";
import { useT } from "@/theme/words";

import { CiBar } from "./CiBar";

export function useMemorySentence(snapshot: SnapshotOut | null) {
  const t = useT();
  const locale = useLocale();
  const mapped =
    snapshot?.totals.reduce((s, r) => s + r.reports_mapped, 0) ?? 0;
  const all = snapshot?.totals.reduce((s, r) => s + r.reports_all, 0) ?? 0;
  return (key: string, window: string[]) =>
    t(`Memory.${key}`, {
      first: window[0] ?? "",
      last: window[window.length - 1] ?? "",
      share: all ? formatShare(mapped / all, locale) : "",
    });
}

export function PairPanel({
  pair,
  ingredient,
  event,
  snapshot,
}: {
  pair: PairOut;
  ingredient: string;
  event: string;
  snapshot: SnapshotOut | null;
}) {
  const t = useT();
  const locale = useLocale();
  const say = useMemorySentence(snapshot);
  const p = pairPanel(pair);
  const caveats = splitCaveats(p.sentences);
  const reports = p.reports ?? 0;
  return (
    <SummaryCard
      title={t("MemoryView.pairHeading", { ingredient, event })}
      id="pair"
      eyebrow={t("MemoryView.pairTitle")}
      data-testid="pair-panel"
    >
      {p.status === "not_available" ? (
        <p>{t("Memory.codes.not_available")}</p>
      ) : (
        <>
          {/* A big number only for reports that exist: a large zero reads as reassurance
              (safety audit F1, rule 3); the sentence says "No reports" instead. */}
          {reports > 0 ? (
            <StatGrid>
              <StatTile
                value={formatCount(reports, locale)}
                label={t("Cards.label.reports", { count: reports })}
                sentence={t("MemoryView.reports", { count: reports })}
              />
            </StatGrid>
          ) : (
            <p className="text-lg font-bold">
              {t("MemoryView.reports", { count: reports })}
            </p>
          )}
          <p className="text-sm text-muted">{t("MemoryView.scopeSuspect")}</p>
          {p.ratio ? <CiBar ratio={p.ratio} /> : null}
          {/* Req 28.5: these caveats stay outside the fold wherever counts are shown. */}
          {caveats.visible.length ? (
            <ul
              className="flex flex-col gap-2 border-s-2 border-line ps-3"
              data-testid="visible-caveats"
            >
              {caveats.visible.map((k) => (
                <li key={k}>{say(k, p.window)}</li>
              ))}
            </ul>
          ) : null}
          <Disclosure
            summary={t("MemoryView.assessmentHeading")}
            className="border-t border-line"
          >
            <ul className="flex flex-col gap-2">
              {caveats.folded.map((k) => (
                <li key={k}>{say(k, p.window)}</li>
              ))}
            </ul>
            {p.pts.length ? (
              <p className="text-sm">
                {t("MemoryView.pts", { pts: p.pts.join(", ") })}
              </p>
            ) : null}
          </Disclosure>
        </>
      )}
      <p className="text-sm text-muted">
        {t("Memory.attribution", { date: formatDate(p.snapshotDate, locale) })}
      </p>
      {p.meddra ? (
        <p className="text-sm text-muted">{t("Memory.meddra")}</p>
      ) : null}
    </SummaryCard>
  );
}

"use client";
/**
 * The FAERS pair panel of a finding detail (Req 16.1, 16.3–16.7): report count, ratio with range
 * and CI bar; the assessment only here, with the screening sentence; limits, window, attribution
 * and the MedDRA notice when Preferred Terms are shown (PT names only in this detail view).
 */
import { useLocale } from "next-intl";

import type { PairOut, SnapshotOut } from "@/api/contracts";
import { formatCount, formatDate, formatShare } from "@/components/format";
import { Card, SectionTitle } from "@/components/ui";
import { pairPanel } from "@/flow/memory";
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
  return (
    <Card aria-labelledby="pair" data-testid="pair-panel">
      <p className="text-sm text-muted">{t("MemoryView.pairTitle")}</p>
      <SectionTitle id="pair">
        {t("MemoryView.pairHeading", { ingredient, event })}
      </SectionTitle>
      {p.status === "not_available" ? (
        <p>{t("Memory.codes.not_available")}</p>
      ) : (
        <>
          <p className="text-lg font-bold">
            {t("MemoryView.reports", { count: p.reports ?? 0 })}
            <span className="sr-only">
              {" "}
              ({formatCount(p.reports ?? 0, locale)})
            </span>
          </p>
          <p className="text-sm text-muted">{t("MemoryView.scopeSuspect")}</p>
          {p.ratio ? <CiBar ratio={p.ratio} /> : null}
          <details className="flex flex-col gap-2">
            <summary className="flex min-h-11 cursor-pointer items-center font-bold">
              {t("MemoryView.assessmentHeading")}
            </summary>
            <ul className="flex flex-col gap-2 pt-2">
              {p.sentences.map((k) => (
                <li key={k}>{say(k, p.window)}</li>
              ))}
            </ul>
            {p.pts.length ? (
              <p className="text-sm">
                {t("MemoryView.pts", { pts: p.pts.join(", ") })}
              </p>
            ) : null}
          </details>
        </>
      )}
      <p className="text-sm text-muted">
        {t("Memory.attribution", { date: formatDate(p.snapshotDate, locale) })}
      </p>
      {p.meddra ? (
        <p className="text-sm text-muted">{t("Memory.meddra")}</p>
      ) : null}
    </Card>
  );
}

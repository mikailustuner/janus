"use client";
/**
 * Pieces every model-kit screen shares (model-kit Req 6): the client hook, the experimental and
 * status badges, the research-use statements and the translated reason codes. Status colours use
 * existing tokens only; red (`--risk`) is never used here (it means real risk).
 */
import { useLocale } from "next-intl";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { useT } from "@/theme/words";
import {
  demoModelKit,
  liveModelKit,
  loadModelKitFixture,
  reasonKey,
  statusBadge,
  type ExpertAudit,
  type Status,
} from "@/modelkit/model";

import { useDemoClient } from "../research/useDemoClient";

export function useModelKitClient() {
  return useDemoClient(liveModelKit, loadModelKitFixture, demoModelKit);
}

export function ExperimentalChip() {
  const t = useT();
  return (
    <span className="chip" data-testid="mk-experimental">
      {t("ModelKit.experimental")}
    </span>
  );
}

const TONE: Record<Status, string> = {
  validated: "",
  not_validated: "border-2 border-line bg-surface text-fg",
  failed: "border-2 border-warn bg-surface text-warn",
};
const MARK: Record<Status, string> = {
  validated: "✓",
  not_validated: "○",
  failed: "△",
};

export function StatusChip({ status }: { status: Status }) {
  const t = useT();
  const b = statusBadge(status);
  return (
    <span
      className={`chip ${TONE[b.tone]}`}
      data-testid="mk-status"
      data-status={status}
    >
      <span aria-hidden>{MARK[status]}</span>
      {t(b.labelKey)}
    </span>
  );
}

/** The two statements every model-kit screen carries (Req 6.1, 6.5). With an expert audit record
 * in the answer (plan 6.4) the review line gives its precision, n and date instead of "Expert
 * review has not yet been done." */
export function Statements({
  recorded,
  audit,
}: {
  recorded: string | null;
  audit?: ExpertAudit | null;
}) {
  const t = useT();
  const locale = useLocale();
  const review = audit
    ? t("ModelKit.expertAudit", {
        precision: new Intl.NumberFormat(locale, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }).format(audit.precision),
        n: audit.n,
        // non-breaking hyphens: the ISO date never breaks across lines at 375 px
        date: audit.date.replaceAll("-", "\u2011"),
      })
    : t("ModelKit.expertReview");
  return (
    <div className="flex flex-col gap-2">
      <p className="card p-4 font-bold" data-testid="mk-research-use">
        {t("ModelKit.researchUse")}
      </p>
      <p
        className="text-sm font-bold"
        role="note"
        data-testid="mk-review"
        data-audit={audit ? "yes" : "no"}
      >
        {review}
      </p>
      {recorded ? (
        <p className="chip self-start" data-testid="mk-demo">
          {t("ModelKit.demo", { date: recorded })}
        </p>
      ) : null}
    </div>
  );
}

/** A reason code in the interface language; a code this version does not know shows as received. */
export function reasonText(
  t: (k: string) => string,
  code: string,
): { text: string; en: boolean } {
  const k = reasonKey(code);
  return k ? { text: t(k), en: false } : { text: code, en: true };
}

export function Reason({ code }: { code: string }) {
  const t = useT();
  const r = reasonText(t, code);
  return <span lang={r.en ? "en" : undefined}>{r.text}</span>;
}

export function ReasonList({
  codes,
  testId,
}: {
  codes: readonly string[];
  testId?: string;
}) {
  return (
    <ul className="m-0 flex list-disc flex-col gap-1 ps-5" data-testid={testId}>
      {codes.map((c) => (
        <li key={c} className="break-words">
          <Reason code={c} />
        </li>
      ))}
    </ul>
  );
}

/**
 * A table that never breaks words: it scrolls inside its own focusable region (the pattern of the
 * other research tables, `tm-table nowrap`), with a visible edge shadow and a hint line so the
 * sideways scroll can be found. The page itself never scrolls sideways.
 */
export function ScrollTable({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  const t = useT();
  const ref = useRef<HTMLDivElement>(null);
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setWide(el.scrollWidth > el.clientWidth + 1);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    if (el.firstElementChild) ro.observe(el.firstElementChild);
    return () => ro.disconnect();
  }, []);
  return (
    <div className="flex max-w-full min-w-0 flex-col gap-1">
      <div
        ref={ref}
        className="card scroll-shadow relative max-w-full overflow-x-auto p-0"
        tabIndex={0}
        role="region"
        aria-label={label}
        data-testid="mk-scroll"
      >
        {children}
      </div>
      {wide ? (
        <p className="text-xs text-muted" data-testid="mk-scroll-hint">
          {t("ModelKit.scrollHint")}
        </p>
      ) : null}
    </div>
  );
}

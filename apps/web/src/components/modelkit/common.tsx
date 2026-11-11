"use client";
/**
 * Pieces every model-kit screen shares (model-kit Req 6): the client hook, the experimental and
 * status badges, the research-use statements and the translated reason codes. Status colours use
 * existing tokens only; red (`--risk`) is never used here (it means real risk).
 */
import { useT } from "@/theme/words";
import {
  demoModelKit,
  liveModelKit,
  loadModelKitFixture,
  reasonKey,
  statusBadge,
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

/** The two statements every model-kit screen carries (Req 6.1, 6.5). */
export function Statements({ recorded }: { recorded: string | null }) {
  const t = useT();
  return (
    <div className="flex flex-col gap-2">
      <p className="card p-4 font-bold" data-testid="mk-research-use">
        {t("ModelKit.researchUse")}
      </p>
      <p className="text-sm font-bold" role="note" data-testid="mk-review">
        {t("ModelKit.expertReview")}
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
    <ul
      className="m-0 flex list-disc flex-col gap-1 ps-5"
      data-testid={testId}
    >
      {codes.map((c) => (
        <li key={c} className="break-words">
          <Reason code={c} />
        </li>
      ))}
    </ul>
  );
}

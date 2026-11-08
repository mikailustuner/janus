"use client";
/**
 * The emergency notice (medical-safety rule 10, Req 1.2, 7.8): first on the home screen and first
 * wherever a safety line or an emergency-symptom event is shown. `--risk` is allowed here only.
 */
import { useT } from "@/theme/words";

import { AlertIcon } from "./icons";
import { useUserRegion } from "./region";

export function EmergencyNotice({
  compact = false,
  slim = false,
}: {
  compact?: boolean;
  /** The home's one-line bar (DP46): one sentence with the number, expandable to the full text. */
  slim?: boolean;
}) {
  const t = useT();
  const region = useUserRegion();
  const emergency = t(`Memory.emergency.${region}`);
  if (slim)
    return (
      <aside
        aria-label={t("Emergency.title")}
        data-testid="emergency-notice"
        className="emergency-slim"
      >
        <details>
          <summary>
            <AlertIcon size={18} className="shrink-0 text-risk" />
            <span>{t("Emergency.line", { emergency })}</span>
            <span aria-hidden className="emergency-chevron">
              ▾
            </span>
          </summary>
          <p>{t("Emergency.text", { emergency })}</p>
        </details>
      </aside>
    );
  return (
    <aside
      aria-label={t("Emergency.title")}
      data-testid="emergency-notice"
      className="flex items-start gap-3 rounded-[var(--radius-card)] border-2 border-risk bg-surface p-3"
    >
      <AlertIcon className="mt-0.5 shrink-0 text-risk" />
      <div className="flex flex-col gap-1">
        {compact ? null : <p className="font-bold">{t("Emergency.title")}</p>}
        <p>{t("Emergency.text", { emergency })}</p>
      </div>
    </aside>
  );
}

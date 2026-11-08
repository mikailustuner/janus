"use client";
/**
 * The safety line of a sensitive event (Req 7.1–7.3): from the `Memory` catalogue, with the
 * user region's emergency or crisis number filled in, never inside the sentence itself.
 */
import type { SafetyLineCode } from "@/vocabulary";
import { useT } from "@/theme/words";

import { AlertIcon } from "./icons";
import { useUserRegion } from "./region";

export function SafetyLine({ code }: { code: SafetyLineCode }) {
  const t = useT();
  const region = useUserRegion();
  return (
    <p
      className="flex items-start gap-2 font-bold text-risk"
      data-testid="safety-line"
      data-code={code}
    >
      <AlertIcon size={20} className="mt-0.5 shrink-0" />
      <span>
        {t(`Memory.codes.${code}`, {
          emergency: t(`Memory.emergency.${region}`),
          crisis: t(`Memory.crisis.${region}`),
        })}
      </span>
    </p>
  );
}

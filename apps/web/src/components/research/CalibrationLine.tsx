"use client";
/**
 * One short line next to every FAERS reporting ratio: how well the method separates known effects
 * from known non-effects (pre-registered calibration study), with a link to the validation page.
 * Secondary in weight; the numbers come from the generated validation file.
 */
import { useLocale } from "next-intl";

import { Link } from "@/i18n/navigation";
import { calibrationValues } from "@/research/validation";
import { useT } from "@/theme/words";

export function CalibrationLine({ className = "" }: { className?: string }) {
  const t = useT();
  const locale = useLocale();
  return (
    <p
      className={`text-xs text-muted ${className}`}
      data-testid="calibration-line"
    >
      {t("Calibration.line", calibrationValues(locale))}{" "}
      <Link
        href="/research/validation-studies#faers"
        data-inline="true"
        className="underline underline-offset-4"
      >
        {t("Calibration.link")}
      </Link>
    </p>
  );
}

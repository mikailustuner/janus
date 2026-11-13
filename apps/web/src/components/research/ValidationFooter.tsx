/** The footer every validation card carries: protocol commit, review note and the two documents. */
import type { ReactNode } from "react";

import { VALIDATION, type CardKey } from "@/research/validation";
import type { Translate } from "@/theme/words";

const EXTERNAL = {
  target: "_blank",
  rel: "noopener noreferrer",
} as const;

function DocLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      className="inline-flex min-h-11 items-center self-start font-bold"
      href={href}
      {...EXTERNAL}
    >
      {children}
    </a>
  );
}

export function Footer({ card, t }: { card: CardKey; t: Translate }) {
  const d = VALIDATION[card];
  return (
    <>
      <p className="text-sm">
        {t("ValidationStudies.preregistered", { commit: d.protocolCommit })}
      </p>
      <p className="text-sm font-bold" role="note">
        {t("ValidationStudies.review")}
      </p>
      <div className="flex flex-wrap gap-x-6">
        <DocLink href={d.protocolUrl}>
          {t("ValidationStudies.protocol")}
        </DocLink>
        <DocLink href={d.resultsUrl}>{t("ValidationStudies.results")}</DocLink>
      </div>
    </>
  );
}

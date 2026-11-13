"use client";
/**
 * The footer every validation card carries: protocol commit, review note, the two documents, the
 * card's numbers as a CSV and the citation of this release (plan D3.2).
 */
import type { ReactNode } from "react";

import { Disclosure } from "@/components/cards";
import { DownloadIcon } from "@/components/icons";
import { Button } from "@/components/ui";
import { citationText, csvFileName, studyRows, toCsv } from "@/research/export";
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
      <div className="flex flex-col gap-2">
        <Button
          variant="secondary"
          className="self-start"
          data-testid={`vs-csv-${card}`}
          onClick={() => download(card)}
        >
          <DownloadIcon size={20} />
          {t("ValidationStudies.csv")}
        </Button>
        <Disclosure summary={t("ValidationStudies.cite")}>
          <p className="text-sm">{t("ValidationStudies.citeIntro")}</p>
          <p
            className="mono text-sm select-all"
            data-testid={`vs-cite-${card}`}
          >
            {citationText()}
          </p>
          <DocLink href={VALIDATION.citation.cffUrl}>CITATION.cff</DocLink>
        </Disclosure>
      </div>
    </>
  );
}

/** Saves the card's numbers as a CSV file; built in the browser, nothing is requested. */
function download(card: CardKey) {
  const blob = new Blob([toCsv(studyRows(card))], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = csvFileName(card);
  a.click();
  URL.revokeObjectURL(url);
}

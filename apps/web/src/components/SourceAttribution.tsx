"use client";
/** Source name and update date of a product card or list row (Req 12.7). */
import type { Candidate } from "@/api/contracts";
import { useT } from "@/theme/words";

export const KNOWN_SOURCES = [
  "titck",
  "openfda_ndc",
  "eu_fr_bdpm",
  "eu_es_cima",
  "eu_it_aifa",
  "wikidata",
];

export function SourceAttribution({ candidate }: { candidate: Candidate }) {
  const t = useT();
  const { source_id, snapshot_date } = candidate.source;
  const source = KNOWN_SOURCES.includes(source_id)
    ? t(`Common.source.${source_id}`)
    : t("Common.source.other", { id: source_id });
  return (
    <>{t("Common.sourceLine", { source, date: snapshot_date.slice(0, 10) })}</>
  );
}

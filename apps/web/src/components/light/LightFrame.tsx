"use client";
/**
 * The frame of every light-face screen (light-face design §10, Req 4.3, 4.5, 5.3; experience
 * Req 29): back to Research, the large title, the rule-7 label, the experimental or prototype
 * status, the review status, "for researchers", the data snapshot and the attributions as a grouped
 * footer. The shell already carries the disclaimer and the emergency notice.
 */
import { useLocale } from "next-intl";
import type { ReactNode } from "react";

import { BackLink, GroupedList, LargeTitle, Row } from "@/components/cards";
import { formatDate } from "@/components/format";
import type { LightSnapshot } from "@/light/model";
import { useT } from "@/theme/words";

export function LightFrame({
  title,
  intro,
  status,
  snapshot,
  attribution,
  children,
}: {
  title: string;
  intro: string;
  status: "experimental" | "prototype" | null;
  snapshot: LightSnapshot | null;
  attribution: string[];
  children: ReactNode;
}) {
  const t = useT();
  const locale = useLocale();
  return (
    <>
      <nav aria-label={t("Light.nav.sections")}>
        <BackLink href="/research">{t("Research.title")}</BackLink>
      </nav>
      <LargeTitle title={title} />
      <p className="max-w-[72ch]">{intro}</p>
      <p className="card p-5 font-bold" data-testid="rule7">
        {t("Light.rule7")}
      </p>
      {status ? (
        <p
          className={`card p-5 ${status === "experimental" ? "font-bold" : ""}`}
          data-testid="light-status"
          role={status === "experimental" ? "note" : undefined}
        >
          {t(`Light.status.${status}`)}
        </p>
      ) : null}
      <ul className="flex flex-col gap-1 px-row-x text-sm text-muted">
        <li>{t("Light.researcherOnly")}</li>
        <li>{t("Light.review")}</li>
      </ul>
      {children}
      {snapshot ? (
        <GroupedList
          header={t("Light.attribution")}
          headingId="light-attribution"
          className="text-sm"
        >
          <Row>
            <p>
              {t("Light.snapshot", {
                onsides: snapshot.onsides_release,
                onsidesDate: formatDate(snapshot.onsides_date, locale),
                faers: formatDate(snapshot.faers_snapshot_date, locale),
                window: snapshot.faers_window.join(", "),
                openfda: formatDate(snapshot.openfda_date, locale),
              })}
            </p>
          </Row>
          {attribution.map((a) => (
            <Row key={a}>
              <p className="text-muted">{a}</p>
            </Row>
          ))}
        </GroupedList>
      ) : null}
    </>
  );
}

"use client";
/**
 * The frame of every light-face screen (light-face design §10, Req 4.3, 4.5, 5.3): the rule-7 label,
 * the experimental or prototype status, the review status, "for researchers", the data snapshot and
 * the attributions. The shell already carries the disclaimer and the emergency notice.
 */
import { useLocale } from "next-intl";
import type { ReactNode } from "react";

import { formatDate } from "@/components/format";
import { ButtonLink, Card, PageTitle } from "@/components/ui";
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
        <ButtonLink href="/research" variant="quiet" className="self-start px-0">
          {t("Light.nav.back")}
        </ButtonLink>
      </nav>
      <PageTitle>{title}</PageTitle>
      <p>{intro}</p>
      <p className="card p-4 font-bold" data-testid="rule7">
        {t("Light.rule7")}
      </p>
      {status ? (
        <p
          className={`card p-4 ${status === "experimental" ? "font-bold" : ""}`}
          data-testid="light-status"
          role={status === "experimental" ? "note" : undefined}
        >
          {t(`Light.status.${status}`)}
        </p>
      ) : null}
      <ul className="flex flex-col gap-1 text-sm text-muted">
        <li>{t("Light.researcherOnly")}</li>
        <li>{t("Light.review")}</li>
      </ul>
      {children}
      {snapshot ? (
        <Card as="aside" className="text-sm">
          <p>
            {t("Light.snapshot", {
              onsides: snapshot.onsides_release,
              onsidesDate: formatDate(snapshot.onsides_date, locale),
              faers: formatDate(snapshot.faers_snapshot_date, locale),
              window: snapshot.faers_window.join(", "),
              openfda: formatDate(snapshot.openfda_date, locale),
            })}
          </p>
          <h2 className="font-semibold">{t("Light.attribution")}</h2>
          <ul className="flex flex-col gap-1">
            {attribution.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </Card>
      ) : null}
    </>
  );
}

"use client";
import { GroupedList, LargeTitle, RowLink } from "@/components/cards";
import { ButtonLink, Chip } from "@/components/ui";
import { useT, useThemeWord } from "@/theme/words";

import { RESEARCH_GROUPS, type ResearchEntry } from "./sections";

/**
 * Researcher area (design §14, Req 24, DP12, Req 29; plan D1): the normal theme (DP48), the Phase 4
 * review status (expert review has not yet been done) and the entries in five groups. The
 * experimental group carries a label and the rule-7 sentence; it is never in the patient flow.
 */
export function Research() {
  const t = useT();
  const w = useThemeWord();
  const title = (e: ResearchEntry) => (e.themeTitle ? w(e.title) : t(e.title));
  return (
    <>
      <LargeTitle title={t("Research.title")} />
      <p className="max-w-[72ch]">{t("Research.intro")}</p>
      <p
        className="card p-5 text-muted"
        role="note"
        data-testid="research-review"
      >
        {t("Research.review")}
      </p>
      {RESEARCH_GROUPS.map((group) => {
        const experimental = group.key === "experimental";
        return (
          <GroupedList
            key={group.key}
            headingId={`research-${group.key}`}
            data-testid={`research-group-${group.key}`}
            header={
              <span className="flex flex-wrap items-center gap-2">
                {t(`Research.groups.${group.key}.title`)}
                {experimental ? (
                  <Chip>{t("Research.experimental")}</Chip>
                ) : null}
              </span>
            }
            footer={
              experimental ? (
                <p className="font-bold">{t("Research.rule7")}</p>
              ) : undefined
            }
          >
            {group.entries.map((e) => (
              <RowLink key={e.href} href={e.href}>
                <span className="sr-only">{t("Light.nav.open")}: </span>
                <span className="flex flex-col gap-0.5">
                  <span className="text-lg">{title(e)}</span>
                  <span className="font-normal text-muted">{t(e.body)}</span>
                </span>
              </RowLink>
            ))}
          </GroupedList>
        );
      })}
      <ButtonLink href="/" variant="secondary" className="self-start">
        {t("Research.back")}
      </ButtonLink>
    </>
  );
}

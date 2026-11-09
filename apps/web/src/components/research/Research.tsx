"use client";
import { GroupedList, LargeTitle, RowLink } from "@/components/cards";
import { ButtonLink } from "@/components/ui";
import { useT, useThemeWord } from "@/theme/words";

const ENTRIES = ["hypotheses", "seance", "validation", "export"] as const;
/** Light-face screens (light-face design §10) and the séance screen (séance design §7). */
const LIVE: Record<(typeof ENTRIES)[number], string> = {
  hypotheses: "/research/hypotheses",
  seance: "/research/seance",
  validation: "/research/validation",
  export: "/research/export",
};

/** Research tools (research-tools Req 4): data quality, the onset table, developers. */
const TOOLS = [
  { key: "dataQuality", href: "/research/data-quality" },
  { key: "onset", href: "/research/faers-onset" },
  { key: "developers", href: "/research/developers" },
] as const;

/**
 * Researcher area (design §14, Req 24, DP12, Req 29): the normal theme (DP48), the rule-7
 * sentence, the Phase 4 review status (expert review has not yet been done) and the four entries as
 * one grouped list of row links.
 */
export function Research() {
  const t = useT();
  const w = useThemeWord();
  const title = (e: (typeof ENTRIES)[number]) =>
    e === "seance"
      ? w("Research.entries.seance.title")
      : t(`Research.entries.${e}.title`);
  return (
    <>
      <LargeTitle title={t("Research.title")} />
      <p className="max-w-[72ch]">{t("Research.intro")}</p>
      <p className="card p-5 font-bold">{t("Research.rule7")}</p>
      <p
        className="card p-5 text-muted"
        role="note"
        data-testid="research-review"
      >
        {t("Research.review")}
      </p>
      <GroupedList>
        {ENTRIES.map((e) => (
          <RowLink key={e} href={LIVE[e]}>
            <span className="sr-only">{t("Light.nav.open")}: </span>
            <span className="flex flex-col gap-0.5">
              <span className="text-lg">{title(e)}</span>
              <span className="font-normal text-muted">
                {t(`Research.entries.${e}.body`)}
              </span>
            </span>
          </RowLink>
        ))}
        <RowLink href="/research/time-machine">
          <span className="sr-only">{t("Light.nav.open")}: </span>
          <span className="flex flex-col gap-0.5">
            <span className="text-lg">{t("TimeMachine.entry.title")}</span>
            <span className="font-normal text-muted">
              {t("TimeMachine.entry.body")}
            </span>
          </span>
        </RowLink>
        {TOOLS.map((e) => (
          <RowLink key={e.href} href={e.href}>
            <span className="sr-only">{t("Light.nav.open")}: </span>
            <span className="flex flex-col gap-0.5">
              <span className="text-lg">
                {t(`Research.tools.${e.key}.title`)}
              </span>
              <span className="font-normal text-muted">
                {t(`Research.tools.${e.key}.body`)}
              </span>
            </span>
          </RowLink>
        ))}
        <RowLink href="/open-data">
          <span className="sr-only">{t("Light.nav.open")}: </span>
          <span className="flex flex-col gap-0.5">
            <span className="text-lg">{t("OpenData.entry.title")}</span>
            <span className="font-normal text-muted">
              {t("OpenData.entry.body")}
            </span>
          </span>
        </RowLink>
        <RowLink href="/cascades">
          <span className="sr-only">{t("Light.nav.open")}: </span>
          <span className="flex flex-col gap-0.5">
            <span className="text-lg">{t("CascadeMap.entry.title")}</span>
            <span className="font-normal text-muted">
              {t("CascadeMap.entry.body")}
            </span>
          </span>
        </RowLink>
      </GroupedList>
      <ButtonLink href="/" variant="secondary" className="self-start">
        {t("Research.back")}
      </ButtonLink>
    </>
  );
}

"use client";
import { ButtonLink, Card, PageTitle } from "@/components/ui";
import { useT, useThemeWord } from "@/theme/words";

const ENTRIES = ["hypotheses", "seance", "validation", "export"] as const;
/** Light-face screens (light-face design §10) and the séance screen (séance design §7). */
const LIVE: Record<(typeof ENTRIES)[number], string> = {
  hypotheses: "/research/hypotheses",
  seance: "/research/seance",
  validation: "/research/validation",
  export: "/research/export",
};

/**
 * Researcher area (design §14, Req 24, DP12): the normal theme (DP48), the rule-7 sentence, the
 * Phase 4 review status (AI-reviewed, pending expert review) and the four entries.
 */
export function Research() {
  const t = useT();
  const w = useThemeWord();
  return (
    <>
      <PageTitle>{t("Research.title")}</PageTitle>
      <p>{t("Research.intro")}</p>
      <p className="card p-4 font-bold">{t("Research.rule7")}</p>
      <p className="card p-4" role="note" data-testid="research-review">
        {t("Research.review")}
      </p>
      <ul className="grid gap-3 sm:grid-cols-2">
        {ENTRIES.map((e) => (
          <Card as="li" key={e}>
            <h2 className="text-lg font-semibold">
              {e === "seance"
                ? w("Research.entries.seance.title")
                : t(`Research.entries.${e}.title`)}
            </h2>
            <p>{t(`Research.entries.${e}.body`)}</p>
            <ButtonLink
              href={LIVE[e]}
              variant="secondary"
              className="self-start"
            >
              {t("Light.nav.open")}
              <span className="sr-only">
                :{" "}
                {e === "seance"
                  ? w("Research.entries.seance.title")
                  : t(`Research.entries.${e}.title`)}
              </span>
            </ButtonLink>
          </Card>
        ))}
        <Card as="li">
          <h2 className="text-lg font-semibold">
            {t("CascadeMap.entry.title")}
          </h2>
          <p>{t("CascadeMap.entry.body")}</p>
          <ButtonLink
            href="/cascades"
            variant="secondary"
            className="self-start"
          >
            {t("Light.nav.open")}
            <span className="sr-only">: {t("CascadeMap.entry.title")}</span>
          </ButtonLink>
        </Card>
      </ul>
      <ButtonLink href="/" variant="secondary" className="self-start">
        {t("Research.back")}
      </ButtonLink>
    </>
  );
}

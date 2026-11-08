"use client";
import { ButtonLink, Card, PageTitle } from "@/components/ui";
import { useT, useThemeWord } from "@/theme/words";

const ENTRIES = ["hypotheses", "seance", "validation", "export"] as const;
/** Light-face screens (light-face design §10); the séance entry belongs to the séance spec. */
const LIVE: Partial<Record<(typeof ENTRIES)[number], string>> = {
  hypotheses: "/research/hypotheses",
  validation: "/research/validation",
  export: "/research/export",
};

/**
 * Researcher area (design §14, Req 24, DP12): the normal theme (DP48), the rule-7 sentence and the
 * four entries; the light-face entries open their screens, the others stay honest empty states.
 */
export function Research() {
  const t = useT();
  const w = useThemeWord();
  return (
    <>
      <PageTitle>{t("Research.title")}</PageTitle>
      <p>{t("Research.intro")}</p>
      <p className="card p-4 font-bold">{t("Research.rule7")}</p>
      <ul className="grid gap-3 sm:grid-cols-2">
        {ENTRIES.map((e) => (
          <Card as="li" key={e}>
            <h2 className="text-lg font-semibold">
              {e === "seance"
                ? w("Research.entries.seance.title")
                : t(`Research.entries.${e}.title`)}
            </h2>
            <p>{t(`Research.entries.${e}.body`)}</p>
            {LIVE[e] ? (
              <ButtonLink
                href={LIVE[e]}
                variant="secondary"
                className="self-start"
              >
                {t("Light.nav.open")}
                <span className="sr-only">
                  : {t(`Research.entries.${e}.title`)}
                </span>
              </ButtonLink>
            ) : (
              <p className="chip">{t("Research.coming")}</p>
            )}
          </Card>
        ))}
      </ul>
      <ButtonLink href="/" variant="secondary" className="self-start">
        {t("Research.back")}
      </ButtonLink>
    </>
  );
}

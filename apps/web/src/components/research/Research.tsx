"use client";
import { ButtonLink, Card, PageTitle } from "@/components/ui";
import { useT, useThemeWord } from "@/theme/words";

const ENTRIES = ["hypotheses", "seance", "validation", "export"] as const;

/**
 * Researcher area shell (design §14, Req 24, DP12): light face, four honest Phase 4 empty states,
 * the rule-7 sentence; no example result, number or hypothesis.
 */
export function Research() {
  const t = useT();
  const w = useThemeWord();
  return (
    <>
      <PageTitle>{w("Research.title")}</PageTitle>
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
            <p className="chip">{t("Research.coming")}</p>
          </Card>
        ))}
      </ul>
      <ButtonLink href="/" variant="secondary" className="self-start">
        {w("Research.back")}
      </ButtonLink>
    </>
  );
}

"use client";
/**
 * The About page: what Janus is, its principles, privacy in one paragraph, the open data sources,
 * the open-source licence and who maintains it. Static text; no request. The wording comes from
 * the README and the existing pages so the five translations stay consistent.
 */
import { LargeTitle } from "@/components/cards";
import { Card, SectionTitle } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { REPO } from "@/research/forResearchers";
import { useT } from "@/theme/words";

const PRINCIPLES = ["p1", "p2", "p3", "p4", "p5", "p6"] as const;
const SOURCES = ["tr", "fr", "es", "us", "ca", "it"] as const;
const EXTERNAL = { target: "_blank", rel: "noopener noreferrer" } as const;
const LINK =
  "inline-flex min-h-11 items-center self-start font-bold underline underline-offset-4";

export function About() {
  const t = useT();
  return (
    <>
      <LargeTitle title={t("About.title")} summary={t("About.summary")} />
      <p className="card p-4 font-bold" data-testid="about-status">
        {t("About.status")}
      </p>
      <Card aria-labelledby="about-what">
        <SectionTitle id="about-what">{t("About.what.title")}</SectionTitle>
        <p className="max-w-[72ch]">{t("About.what.body")}</p>
      </Card>
      <Card aria-labelledby="about-principles">
        <SectionTitle id="about-principles">
          {t("About.principles.title")}
        </SectionTitle>
        <ul className="flex max-w-[72ch] list-disc flex-col gap-2 pl-5">
          {PRINCIPLES.map((p) => (
            <li key={p}>{t(`About.principles.${p}`)}</li>
          ))}
        </ul>
      </Card>
      <Card aria-labelledby="about-privacy">
        <SectionTitle id="about-privacy">
          {t("About.privacy.title")}
        </SectionTitle>
        <p className="max-w-[72ch]">{t("About.privacy.body")}</p>
        <Link href="/privacy" className={LINK}>
          {t("About.privacy.link")}
        </Link>
      </Card>
      <Card aria-labelledby="about-sources">
        <SectionTitle id="about-sources">
          {t("About.sources.title")}
        </SectionTitle>
        <p className="max-w-[72ch]">{t("About.sources.intro")}</p>
        <ul className="flex flex-col gap-1">
          {SOURCES.map((s) => (
            <li key={s}>{t(`About.sources.${s}`)}</li>
          ))}
        </ul>
        <a className={LINK} href={`${REPO}/blob/main/NOTICE`} {...EXTERNAL}>
          {t("About.sources.link")}
        </a>
      </Card>
      <Card aria-labelledby="about-open-source">
        <SectionTitle id="about-open-source">
          {t("About.openSource.title")}
        </SectionTitle>
        <p className="max-w-[72ch]">{t("About.openSource.body")}</p>
        <ul className="flex flex-wrap gap-x-4">
          <li>
            <a className={LINK} href={REPO} {...EXTERNAL}>
              {t("About.openSource.repo")}
            </a>
          </li>
          <li>
            <Link href="/research" className={LINK}>
              {t("About.openSource.research")}
            </Link>
          </li>
        </ul>
      </Card>
      <Card aria-labelledby="about-maintainer">
        <SectionTitle id="about-maintainer">
          {t("About.maintainer.title")}
        </SectionTitle>
        <p className="max-w-[72ch]">{t("About.maintainer.body")}</p>
      </Card>
    </>
  );
}

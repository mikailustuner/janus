import { useTranslations } from "next-intl";

import { ButtonLink, PageTitle } from "@/components/ui";

// Localized not-found page for unknown paths under a locale (Req 8.4).
export default function NotFound() {
  const t = useTranslations("NotFound");
  return (
    <>
      <PageTitle>{t("title")}</PageTitle>
      <p>{t("body")}</p>
      <ButtonLink href="/" className="self-start">
        {t("home")}
      </ButtonLink>
    </>
  );
}

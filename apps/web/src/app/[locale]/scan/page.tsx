import { useTranslations } from "next-intl";

import { ButtonLink, PageTitle } from "@/components/ui";

// Placeholder until task 13 (scanning) replaces it; the demo shows the whole flow meanwhile.
export default function ScanPage() {
  const t = useTranslations();
  return (
    <>
      <PageTitle>{t("Scan.title")}</PageTitle>
      <p className="card p-4">{t("Scan.coming")}</p>
      <ButtonLink href="/demo" className="self-start">
        {t("Home.demo")}
      </ButtonLink>
    </>
  );
}

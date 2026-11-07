import { useLocale, useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { localeNames, routing } from "@/i18n/routing";

export default function HomePage() {
  const t = useTranslations();
  const current = useLocale();

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col gap-8 p-6">
      <nav aria-label={t("LocaleSwitcher.label")}>
        <ul className="flex flex-wrap gap-3 text-sm">
          {routing.locales.map((locale) => (
            <li key={locale}>
              <Link
                href="/"
                locale={locale}
                lang={locale}
                aria-current={locale === current ? "page" : undefined}
                className="underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 aria-[current=page]:font-semibold"
              >
                {localeNames[locale]}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <main className="flex flex-col gap-4">
        <h1 className="text-3xl font-semibold">{t("Home.title")}</h1>
        <p>{t("Home.status")}</p>
      </main>

      <footer className="mt-auto border-t pt-4 text-sm">
        <p>{t("Disclaimer.text")}</p>
      </footer>
    </div>
  );
}

import type { Metadata, Viewport } from "next";
import { NextIntlClientProvider } from "next-intl";
import { Suspense } from "react";
import { getLocale, getTranslations } from "next-intl/server";

import { Shell } from "@/components/Shell";
import { routing } from "@/i18n/routing";
import { fontVariables } from "@/theme/fonts";
import { PREPAINT_SOURCE } from "@/theme/prepaint";

import "../globals.css";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("Metadata");
  return {
    title: t("title"),
    description: t("description"),
    referrer: "no-referrer",
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default async function LocaleLayout({
  children,
}: LayoutProps<"/[locale]">) {
  const locale = await getLocale();
  return (
    <html
      lang={locale}
      className={fontVariables}
      data-theme-style="two-faces"
      data-face="shadow"
      data-large-text="off"
      data-reduce-transparency="off"
      suppressHydrationWarning
    >
      <head>
        {/* Theme, face, large text and reduced transparency before the first paint (Req 6.7). */}
        <script dangerouslySetInnerHTML={{ __html: PREPAINT_SOURCE }} />
      </head>
      <body className="antialiased">
        <NextIntlClientProvider>
          {/* Dynamic paths (the not-found catch-all) render the shell on the client. */}
          <Suspense
            fallback={
              <main className="mx-auto max-w-[720px] p-4">{children}</main>
            }
          >
            <Shell>{children}</Shell>
          </Suspense>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}

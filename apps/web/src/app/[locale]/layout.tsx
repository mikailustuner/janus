import type { Metadata, Viewport } from "next";
import { NextIntlClientProvider } from "next-intl";
import { Suspense } from "react";
import { getLocale, getTranslations } from "next-intl/server";

import { ServiceWorker } from "@/components/ServiceWorker";
import { Shell } from "@/components/Shell";
import { routing } from "@/i18n/routing";
import { fontVariables } from "@/theme/fonts";
import { OG_LOCALE, OG_SIZE, ogImageUrl } from "@/seo/metadata";
import { SITE_URL } from "@/seo/routes";
import { jsonLdScript, structuredData } from "@/seo/structured-data";
import { PREPAINT_SOURCE } from "@/theme/prepaint";

import "../globals.css";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  const t = await getTranslations("Metadata");
  const images = [{ url: ogImageUrl(locale), ...OG_SIZE, alt: t("title") }];
  return {
    metadataBase: new URL(SITE_URL),
    title: { default: t("title"), template: `%s · ${t("title")}` },
    description: t("description"),
    openGraph: {
      type: "website",
      siteName: t("title"),
      title: t("title"),
      description: t("description"),
      locale: OG_LOCALE[locale],
      images,
    },
    twitter: { card: "summary_large_image", images },
    referrer: "no-referrer",
    manifest: "/manifest.webmanifest",
    icons: { icon: "/icon.svg" },
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
  const t = await getTranslations("Metadata");
  const data = structuredData({
    locale,
    name: t("title"),
    description: t("description"),
  });
  return (
    <html
      lang={locale}
      className={fontVariables}
      data-theme-style="two-faces"
      data-large-text="off"
      data-reduce-transparency="off"
      suppressHydrationWarning
    >
      <head>
        {/* Theme, large text and reduced transparency before the first paint (Req 6.7). */}
        <script dangerouslySetInnerHTML={{ __html: PREPAINT_SOURCE }} />
        {/* Structured data (WebSite, WebApplication): data, not script, so the CSP never runs it. */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLdScript(data) }}
        />
      </head>
      <body className="antialiased">
        <ServiceWorker />
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

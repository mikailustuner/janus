import type { MetadataRoute } from "next";

import {
  INDEXED,
  languageAlternates,
  LOCALES,
  localizedPath,
  SITE_URL,
} from "@/seo/routes";

// The build time (set in next.config.ts); a page changes only with a new build.
const BUILT = process.env.NEXT_PUBLIC_JANUS_BUILD_TIME;

/** Every indexable public page in every locale, with its hreflang alternates. */
export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = BUILT ? new Date(BUILT) : new Date();
  return INDEXED.flatMap((route) => {
    const languages = Object.fromEntries(
      Object.entries(languageAlternates(route.path)).map(
        ([lang, path]) => [lang, `${SITE_URL}${path}`] as const,
      ),
    );
    return LOCALES.map((locale) => ({
      url: `${SITE_URL}${localizedPath(locale, route.path)}`,
      lastModified,
      changeFrequency: route.changeFrequency,
      priority: route.priority,
      alternates: { languages },
    }));
  });
}

import type { MetadataRoute } from "next";

import { NOINDEX, SITE_URL } from "@/seo/routes";

/**
 * Plain directives only (no content signals): the edge adds its own managed block in front of
 * this file. Crawlers may fetch the public pages; /api/, the doctor page /o and the per-user
 * pages (routes.ts, NOINDEX) are not for them. Pages are under a locale prefix, so each rule uses
 * the `*` wildcard for the locale segment.
 */
export default function robots(): MetadataRoute.Robots {
  const disallow = [
    "/api/",
    "/o/",
    "/o$",
    ...Object.keys(NOINDEX).map((path) => `/*${path}$`),
  ];
  return {
    rules: [{ userAgent: "*", allow: "/", disallow }],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}

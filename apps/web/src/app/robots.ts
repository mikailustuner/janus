import type { MetadataRoute } from "next";

import { SITE_URL } from "@/seo/routes";

/**
 * Plain directives only (no content signals): the edge adds its own managed block in front of
 * this file. Only /api/ and the doctor page /o are blocked. The per-user pages (routes.ts, NOINDEX)
 * stay crawlable on purpose: a page blocked here cannot show crawlers its noindex tag, so it could
 * still be listed from outside links.
 */
export default function robots(): MetadataRoute.Robots {
  const disallow = ["/api/", "/o/", "/o$"];
  return {
    rules: [{ userAgent: "*", allow: "/", disallow }],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}

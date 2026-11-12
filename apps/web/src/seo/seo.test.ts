import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

import { createTranslator } from "next-intl";
import { describe, expect, it, vi } from "vitest";

import robots from "@/app/robots";
import sitemap from "@/app/sitemap";
import { findContestTerms } from "@/i18n/forbidden-phrases";
import { OG_COLORS } from "@/theme/og";

import { pageMetadata } from "./metadata";
import { INDEXED, LOCALES, NOINDEX, SITE_URL } from "./routes";
import { jsonLdScript, structuredData } from "./structured-data";

vi.mock("next-intl/server", async () => {
  const { readFileSync: read } = await import("node:fs");
  return {
    getTranslations: async ({ locale }: { locale: string }) =>
      createTranslator({
        locale: locale as "en",
        messages: JSON.parse(
          read(
            join(import.meta.dirname, `../../messages/${locale}.json`),
            "utf8",
          ),
        ),
      }),
  };
});

const appDir = join(import.meta.dirname, "../app");

/** Locale-less routes of every page under src/app/[locale], except the catch-all. */
function pageRoutes(): { route: string; file: string }[] {
  const out: { route: string; file: string }[] = [];
  const walk = (dir: string) => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const p = join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.name === "page.tsx") {
        const route = "/" + relative(join(appDir, "[locale]"), dir);
        out.push({ route: route === "/" ? "" : route, file: p });
      }
    }
  };
  walk(join(appDir, "[locale]"));
  return out.filter((r) => !r.route.includes("[...rest]"));
}

describe("route decisions", () => {
  it("every page is either indexed or noindex, never both", () => {
    const indexed = new Set(INDEXED.map((r) => r.path));
    const noindex = new Set(Object.keys(NOINDEX));
    for (const { route } of pageRoutes()) {
      expect(indexed.has(route) !== noindex.has(route), route).toBe(true);
    }
    for (const path of [...indexed, ...noindex]) {
      expect(
        pageRoutes().some((r) => r.route === path),
        path,
      ).toBe(true);
    }
  });

  it("noindex pages say noindex; indexed pages call pageMetadata with their id", () => {
    for (const { route, file } of pageRoutes()) {
      const source = readFileSync(file, "utf8");
      const indexed = INDEXED.find((r) => r.path === route);
      if (indexed) {
        expect(source, route).toContain(
          `pageMetadata(locale, "${indexed.id}")`,
        );
        expect(source, route).not.toContain("noIndex");
      } else {
        expect(source, route).toContain("export const metadata = noIndex;");
      }
    }
  });
});

describe("sitemap", () => {
  const entries = sitemap();
  const urls = entries.map((e) => e.url);

  it("has every indexable route in every locale", () => {
    expect(entries).toHaveLength(INDEXED.length * LOCALES.length);
    for (const route of INDEXED)
      for (const locale of LOCALES)
        expect(urls).toContain(`${SITE_URL}/${locale}${route.path}`);
  });

  it("has no noindex page, no API route and no duplicate", () => {
    for (const path of Object.keys(NOINDEX))
      for (const locale of LOCALES)
        expect(urls).not.toContain(`${SITE_URL}/${locale}${path}`);
    expect(urls.some((u) => u.includes("/api/") || u.includes("/o/"))).toBe(
      false,
    );
    expect(new Set(urls).size).toBe(urls.length);
  });

  it("lists the five locales and x-default as alternates, pointing at the English page", () => {
    for (const entry of entries) {
      const languages = entry.alternates?.languages as Record<string, string>;
      expect(Object.keys(languages).sort()).toEqual(
        [...LOCALES, "x-default"].sort(),
      );
      expect(languages["x-default"]).toBe(languages.en);
      expect(languages[entry.url.split("/")[3] ?? ""]).toBe(entry.url);
    }
  });

  it("has a modified date, a change frequency and a priority", () => {
    for (const entry of entries) {
      expect(entry.lastModified).toBeInstanceOf(Date);
      expect(entry.changeFrequency).toBeTruthy();
      expect(entry.priority).toBeGreaterThan(0);
      expect(entry.priority).toBeLessThanOrEqual(1);
    }
  });

  it("never mentions the competition", () => {
    expect(findContestTerms(JSON.stringify(entries))).toEqual([]);
  });
});

describe("robots", () => {
  const result = robots();
  const rule = (Array.isArray(result.rules) ? result.rules[0] : result.rules)!;
  const disallow = [rule.disallow].flat().filter(Boolean) as string[];

  /** Robots matching: `*` any run, `$` end of path, otherwise a prefix. */
  const blocked = (pattern: string, path: string) =>
    new RegExp(
      "^" +
        pattern
          .replace(/[.+?^{}()|[\]\\]/g, "\\$&")
          .replace(/\*/g, ".*")
          .replace(/\$$/, "$$$$")
          .replace(/\$\$$/, "$"),
    ).test(path);
  const isBlocked = (path: string) => disallow.some((p) => blocked(p, path));

  it("points at the sitemap and uses plain directives", () => {
    expect(result.sitemap).toBe(`${SITE_URL}/sitemap.xml`);
    expect(rule.userAgent).toBe("*");
    expect(rule.allow).toBe("/");
  });

  it("disallows the API, the doctor page and every noindex route in every locale", () => {
    expect(isBlocked("/api/health")).toBe(true);
    expect(isBlocked("/o")).toBe(true);
    expect(isBlocked("/o/anything")).toBe(true);
    for (const path of Object.keys(NOINDEX))
      for (const locale of LOCALES)
        expect(isBlocked(`/${locale}${path}`), `/${locale}${path}`).toBe(true);
  });

  it("does not block any indexed route, the sitemap or the Next assets", () => {
    for (const route of INDEXED)
      for (const locale of LOCALES)
        expect(isBlocked(`/${locale}${route.path}`), route.id).toBe(false);
    expect(isBlocked("/sitemap.xml")).toBe(false);
    expect(isBlocked("/_next/static/chunk.js")).toBe(false);
  });

  it("never mentions the competition", () => {
    expect(findContestTerms(JSON.stringify(result))).toEqual([]);
  });
});

describe("page metadata", () => {
  it("has title, description, canonical, hreflang, Open Graph and Twitter card", async () => {
    const meta = await pageMetadata("tr", "privacy");
    expect(meta.title).toBe("Gizlilik");
    expect(meta.description).toContain("Janus");
    expect(meta.alternates?.canonical).toBe("/tr/privacy");
    expect(meta.alternates?.languages).toEqual({
      en: "/en/privacy",
      tr: "/tr/privacy",
      de: "/de/privacy",
      fr: "/fr/privacy",
      es: "/es/privacy",
      "x-default": "/en/privacy",
    });
    expect(meta.openGraph).toMatchObject({
      type: "website",
      locale: "tr_TR",
      url: "/tr/privacy",
    });
    expect(meta.twitter).toMatchObject({ card: "summary_large_image" });
    const images = meta.openGraph?.images as { url: string }[];
    expect(images[0]?.url).toBe(`${SITE_URL}/tr/og.png`);
  });

  it("does not repeat the name in a title that already has it", async () => {
    const meta = await pageMetadata("en", "about");
    expect(meta.title).toEqual({ absolute: "About Janus" });
  });

  it("gives the home an absolute title with the tagline", async () => {
    const meta = await pageMetadata("en", "home");
    expect(meta.title).toEqual({
      absolute: "Janus · A check of the medicines at home",
    });
    expect(meta.alternates?.canonical).toBe("/en");
  });

  it("has a unique title and description per page and locale, within search-result length", async () => {
    for (const locale of LOCALES) {
      const titles = new Set<string>();
      const descriptions = new Set<string>();
      for (const route of INDEXED) {
        const meta = await pageMetadata(locale, route.id);
        const title =
          typeof meta.title === "string"
            ? meta.title
            : (meta.title as { absolute: string }).absolute;
        titles.add(title);
        descriptions.add(String(meta.description));
        expect(
          String(meta.description).length,
          `${locale} ${route.id}`,
        ).toBeLessThanOrEqual(200);
        expect(findContestTerms(JSON.stringify(meta))).toEqual([]);
      }
      expect(titles.size, locale).toBe(INDEXED.length);
      expect(descriptions.size, locale).toBe(INDEXED.length);
    }
  });
});

describe("structured data", () => {
  const data = structuredData({
    locale: "de",
    name: "Janus",
    description: "x",
  });

  it("is a WebSite and a WebApplication with no medical type", () => {
    expect(data.map((d) => d["@type"])).toEqual(["WebSite", "WebApplication"]);
    const text = JSON.stringify(data);
    expect(text).not.toMatch(/Medical|Drug|Health/);
    const [site, app] = data;
    expect(site).toMatchObject({
      name: "Janus",
      url: `${SITE_URL}/de`,
      inLanguage: "de",
    });
    expect(app).toMatchObject({
      applicationCategory: "ReferenceApplication",
      isAccessibleForFree: true,
      offers: { price: "0" },
      license: "https://www.apache.org/licenses/LICENSE-2.0",
      isBasedOn: { codeRepository: "https://github.com/mikailustuner/janus" },
      author: { name: "Mikail Üstüner" },
    });
    expect(text).not.toMatch(/@[\w-]+\.\w|email|telephone/i);
    expect(findContestTerms(text)).toEqual([]);
  });

  it("escapes < so the data cannot close the script tag", () => {
    expect(jsonLdScript({ a: "</script><b>" })).not.toContain("<");
    expect(JSON.parse(jsonLdScript({ a: "</script>" }))).toEqual({
      a: "</script>",
    });
  });
});

describe("social image", () => {
  it("uses the Night Pharmacy tokens", () => {
    const css = readFileSync(
      join(import.meta.dirname, "../theme/tokens.css"),
      "utf8",
    ).toLowerCase();
    for (const value of Object.values(OG_COLORS))
      expect(css, value).toContain(value.toLowerCase());
  });
});

describe("findContestTerms", () => {
  it("matches the words and their inflections, not other words", () => {
    expect(findContestTerms("The Kiroween 2026 Hackathon on Devpost")).toEqual([
      "kiroween",
      "hackathon",
      "devpost",
    ]);
    expect(findContestTerms("yarışması")).toEqual(["yarışma"]);
    expect(
      findContestTerms("Wettbewerb, concours, concurso, competition, contest"),
    ).toHaveLength(5);
    expect(findContestTerms("Kiro MCP client configuration; context")).toEqual(
      [],
    );
  });
});

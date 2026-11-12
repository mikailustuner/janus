// The About page (five locales × two themes, both viewports by project): axe, no horizontal
// scroll, 44 px targets, the status line, the links, no forbidden phrase and no mention of the
// competition. The SEO head of the home page (canonical, hreflang, Open Graph, Twitter card,
// JSON-LD, no CSP violation), noindex on a per-user page, robots.txt and sitemap.xml.
// Screenshots when ABOUT_SHOTS_DIR is set.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import {
  findContestTerms,
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";

import {
  expectNoAxeViolations,
  expectNoHorizontalScroll,
  expectTouchTargets,
  LOCALES,
  stubApi,
  THEMES,
  useTheme,
} from "./helpers";

const messages = Object.fromEntries(
  LOCALES.map((l) => [
    l,
    JSON.parse(
      readFileSync(join(import.meta.dirname, `../messages/${l}.json`), "utf8"),
    ),
  ]),
);
const SHOTS = process.env.ABOUT_SHOTS_DIR;

for (const theme of THEMES)
  for (const locale of LOCALES)
    test(`about, ${locale}, ${theme}`, async ({ page }, info) => {
      await useTheme(page, theme);
      await stubApi(page, {});
      await page.goto(`/${locale}/about`);
      const m = messages[locale];
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(
        m.About.title,
      );
      await expect(page.getByTestId("about-status")).toHaveText(m.About.status);
      await expect(page.getByTestId("disclaimer")).toHaveText(
        m.Disclaimer.text,
      );
      const main = page.getByRole("main");
      await expect(main.locator(`a[href="/${locale}/privacy"]`)).toBeVisible();
      await expect(
        main.locator('a[href="https://github.com/mikailustuner/janus"]'),
      ).toBeVisible();
      await expect(
        main.locator(
          'a[href="https://github.com/mikailustuner/janus/blob/main/NOTICE"]',
        ),
      ).toBeVisible();
      await expect(main.locator(`a[href="/${locale}/research"]`)).toBeVisible();
      await page.waitForLoadState("networkidle");
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      const text = await page.locator("body").innerText();
      expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
      expect(findContestTerms(text)).toEqual([]);
      expect(text).not.toMatch(/[\w.-]+@[\w-]+\.\w/);
      if (SHOTS) {
        mkdirSync(SHOTS, { recursive: true });
        await page.screenshot({
          path: join(
            SHOTS,
            `about-${locale}-${info.project.name}-${theme}.png`,
          ),
          fullPage: true,
        });
      }
    });

test("the About page is linked from the footer of the home", async ({
  page,
}) => {
  await stubApi(page, {});
  await page.goto("/en");
  await expect(
    page.getByRole("contentinfo").locator('a[href="/en/about"]'),
  ).toBeVisible();
});

test("the home has canonical, hreflang, Open Graph, Twitter card and JSON-LD, and the CSP blocks nothing", async ({
  page,
}) => {
  const violations: string[] = [];
  page.on("console", (msg) => {
    if (/content security policy/i.test(msg.text()))
      violations.push(msg.text());
  });
  await stubApi(page, {});
  const response = await page.goto("/de");
  expect(response?.headers()["content-security-policy"]).toBeTruthy();
  await page.waitForLoadState("networkidle");
  expect(violations).toEqual([]);
  const href = (sel: string) =>
    page
      .locator(sel)
      .evaluateAll((els) => els.map((e) => e.getAttribute("href")));
  const content = (sel: string) =>
    page.locator(sel).first().getAttribute("content");
  expect(await href('link[rel="canonical"]')).toEqual([
    "https://janusmeds.org/de",
  ]);
  const alternates = await page
    .locator('link[rel="alternate"][hreflang]')
    .evaluateAll((els) =>
      Object.fromEntries(
        els.map((e) => [e.getAttribute("hreflang"), e.getAttribute("href")]),
      ),
    );
  expect(alternates).toEqual({
    en: "https://janusmeds.org/en",
    tr: "https://janusmeds.org/tr",
    de: "https://janusmeds.org/de",
    fr: "https://janusmeds.org/fr",
    es: "https://janusmeds.org/es",
    pt: "https://janusmeds.org/pt",
    "x-default": "https://janusmeds.org/en",
  });
  expect(await content('meta[property="og:image"]')).toBe(
    "https://janusmeds.org/de/og.png",
  );
  expect(await content('meta[property="og:locale"]')).toBe("de_DE");
  expect(await content('meta[name="twitter:card"]')).toBe(
    "summary_large_image",
  );
  await expect(page.locator('meta[name="robots"]')).toHaveCount(0);
  const ld = await page
    .locator('script[type="application/ld+json"]')
    .evaluateAll((els) => els.map((e) => JSON.parse(e.textContent ?? "null")));
  expect(ld).toHaveLength(1);
  expect(ld[0].map((d: { "@type": string }) => d["@type"])).toEqual([
    "WebSite",
    "WebApplication",
  ]);
  expect(ld[0][1]).toMatchObject({
    applicationCategory: "ReferenceApplication",
    isAccessibleForFree: true,
    inLanguage: "de",
  });
  // The social image is a PNG.
  const image = await page.request.get("/de/og.png");
  expect(image.headers()["content-type"]).toBe("image/png");
});

test("a per-user page is noindex", async ({ page }) => {
  await stubApi(page, {});
  await page.goto("/en/results");
  expect(
    await page.locator('meta[name="robots"]').getAttribute("content"),
  ).toBe("noindex, nofollow");
  await expect(page.locator('link[rel="canonical"]')).toHaveCount(0);
});

test("robots.txt and sitemap.xml", async ({ request }) => {
  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toContain("Disallow: /api/");
  expect(robots).toContain("Sitemap: https://janusmeds.org/sitemap.xml");
  expect(findContestTerms(robots)).toEqual([]);
  const sitemap = await (await request.get("/sitemap.xml")).text();
  expect(sitemap).toContain("<loc>https://janusmeds.org/tr/about</loc>");
  expect(sitemap).not.toContain("/scan");
  expect(sitemap).not.toContain("/api/");
  expect(findContestTerms(sitemap)).toEqual([]);
});

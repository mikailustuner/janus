// C1–C3 on every route built so far, 5 locales × 2 themes (and both viewports, by project):
// axe (WCAG 2.2 A/AA), no horizontal scroll, 44 px targets, the disclaimer on every screen, the
// emergency notice first on home, no forbidden phrase, Glass without theme-device words.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { themeWords } from "../src/i18n/reassurance";

import {
  stubApi,
  expectNoAxeViolations,
  expectNoHorizontalScroll,
  expectTouchTargets,
  LOCALES,
  recordRequests,
  THEMES,
  useTheme,
} from "./helpers";

const messages = Object.fromEntries(
  LOCALES.map((l) => [
    l,
    JSON.parse(
      readFileSync(
        join(import.meta.dirname, "../messages", `${l}.json`),
        "utf8",
      ),
    ),
  ]),
);

const PLAIN = [
  "",
  "/start",
  "/settings",
  "/demo",
  "/demo/codes",
  "/research",
  "/scan",
  "/confirm",
  "/privacy",
  "/donate",
  "/donate/delete",
  "/note/withdraw",
  "/report",
  "/no-such-page",
];
const DEMO = [
  "/medicines",
  "/medicines/info#demo-istanbul-0",
  "/passport",
  "/passport/item#demo-istanbul-0",
  "/passport/products#demo-istanbul-0",
  "/timeline",
  "/results",
  "/results/finding#1",
  "/results/summary",
  "/memory",
  "/note",
  "/demo/doctor",
  "/donate",
  "/cascades",
  "/report#src=list",
];

async function demoSession(page: Page) {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
}

async function checks(
  page: Page,
  locale: (typeof LOCALES)[number],
  theme: string,
  route: string,
) {
  await expect(page.getByTestId("disclaimer")).toHaveText(
    messages[locale].Disclaimer.text,
  );
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  const text = await page.locator("body").innerText();
  expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
  if (theme === "glass")
    expect(findForbiddenPhrases(text, themeWords[locale])).toEqual([]);
  if (route === "") {
    // The home is full-bleed (DP46): the notice is the first marked element of the page body.
    const first = await page
      .locator("main [data-testid]")
      .first()
      .getAttribute("data-testid");
    expect(first).toBe("emergency-notice");
  }
}

// CI runs en and tr only (E2E_LOCALES=en,tr); the full matrix runs locally (owner decision).
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

for (const theme of THEMES)
  for (const locale of locales) {
    test(`plain routes, ${locale}, ${theme}`, async ({ page }) => {
      await useTheme(page, theme);
      // No API in these checks: /privacy shows "the region cannot be shown right now".
      await stubApi(page, {
        "/privacy/storage": { status: 503, body: { error: "unavailable" } },
      });
      for (const route of PLAIN) {
        await page.goto(`/${locale}${route}`);
        await page.waitForLoadState("networkidle");
        await checks(page, locale, theme, route);
      }
    });
    test(`demo routes, ${locale}, ${theme}`, async ({ page }) => {
      await useTheme(page, theme);
      await demoSession(page);
      const requests = recordRequests(page);
      for (const route of DEMO) {
        await page.goto(`/${locale}${route}`);
        await page.waitForLoadState("networkidle");
        await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, {
          timeout: 15_000,
        });
        await expect(page.getByTestId("demo-label")).toBeVisible();
        await checks(page, locale, theme, route);
      }
      // C4: in demo mode nothing reaches the API.
      expect(
        requests
          .filter((r) => new URL(r.url()).pathname.startsWith("/api/"))
          .map((r) => r.url()),
      ).toEqual([]);
      expect(
        requests.every(
          (r) =>
            new URL(r.url()).origin === new URL(page.url()).origin ||
            r.url().startsWith("data:") ||
            r.url().startsWith("blob:"),
        ),
      ).toBe(true);
    });
  }

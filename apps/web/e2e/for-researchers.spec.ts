// "Janus for researchers" (spec for-researchers, requirements 1-5): the static page in five
// locales × two themes (and both viewports, by project): axe, no horizontal scroll, 44 px targets,
// the disclaimer, no forbidden phrase, the status line, the links from the Research index, the
// footer and the Open data page, and a copy button that puts the code on the clipboard.
// Screenshots when RESEARCH_SHOTS_DIR is set.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { ONSET_EXAMPLE } from "../src/research/forResearchers";

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
const SHOTS = process.env.RESEARCH_SHOTS_DIR;
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

for (const theme of THEMES)
  for (const locale of locales)
    test(`for researchers, ${locale}, ${theme}`, async ({ page }, info) => {
      await useTheme(page, theme);
      await stubApi(page, {});
      await page.goto(`/${locale}/research/for-researchers`);
      const m = messages[locale];
      await expect(page.getByRole("main").getByTestId("fr-status")).toHaveText(
        m.ForResearchers.status,
      );
      await expect(
        page.getByRole("main").getByTestId("fr-notes-status"),
      ).toHaveText(m.ForResearchers.notes.status);
      await expect(page.getByTestId("disclaimer")).toHaveText(
        m.Disclaimer.text,
      );
      await page.waitForLoadState("networkidle");
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      const text = await page.locator("body").innerText();
      expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
      if (SHOTS && (locale === "en" || locale === "tr")) {
        mkdirSync(SHOTS, { recursive: true });
        await page.screenshot({
          path: join(
            SHOTS,
            `for-researchers-${locale}-${info.project.name}-${theme}.png`,
          ),
          fullPage: true,
        });
      }
    });

test("the page is linked from the Research index, the footer and the Open data page", async ({
  page,
}) => {
  await stubApi(page, {});
  const href = "/en/research/for-researchers";
  await page.goto("/en/research");
  await expect(page.locator(`main a[href="${href}"]`)).toBeVisible();
  await page.goto("/en/open-data");
  await expect(page.locator(`main a[href="${href}"]`)).toBeVisible();
  await expect(page.locator(`footer a[href="${href}"]`)).toBeVisible();
});

test("the copy button copies the worked example", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await stubApi(page, {});
  await page.goto("/en/research/for-researchers");
  await page.getByTestId("dev-copy-fr-example-code").click();
  await expect(page.locator("#dev-fr-example-code-status")).toHaveText(
    messages.en.Developers.copied,
  );
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
    ONSET_EXAMPLE,
  );
});

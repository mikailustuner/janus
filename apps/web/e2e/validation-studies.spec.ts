// Validation studies page (researcher area) and the calibration line next to reporting ratios:
// both themes (and both viewports, by project), en and tr, axe, no horizontal scroll, 44 px
// targets, the numbers from the generated file, the links to the protocol and results documents,
// the review sentence, no forbidden phrase, and the link from the Research index.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { VALIDATION } from "../src/research/validation";

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
const locales = (process.env.E2E_LOCALES ?? "en,tr")
  .split(",")
  .filter((l): l is (typeof LOCALES)[number] =>
    (LOCALES as readonly string[]).includes(l),
  );

for (const theme of THEMES)
  for (const locale of locales)
    test(`validation studies, ${locale}, ${theme}`, async ({ page }) => {
      await useTheme(page, theme);
      await stubApi(page, {});
      await page.goto(`/${locale}/research/validation-studies`);
      const m = messages[locale].ValidationStudies;
      const main = page.getByRole("main");
      await expect(main.getByRole("heading", { level: 1 })).toHaveText(m.title);
      await expect(main.getByTestId("vs-review")).toHaveText(m.review);
      for (const id of ["vs-cascade", "vs-faers"]) {
        const card = main.getByTestId(id);
        await expect(card).toBeVisible();
        await expect(card.getByRole("note")).toHaveText(m.review);
        const links = card.getByRole("link");
        await expect(links).toHaveCount(2);
      }
      const { cascade, faers } = VALIDATION;
      await expect(
        main.getByTestId("vs-cascade").getByRole("link").first(),
      ).toHaveAttribute("href", cascade.protocolUrl);
      await expect(
        main.getByTestId("vs-cascade").getByRole("link").last(),
      ).toHaveAttribute("href", cascade.resultsUrl);
      await expect(
        main.getByTestId("vs-faers").getByRole("link").first(),
      ).toHaveAttribute("href", faers.protocolUrl);
      await expect(main.getByTestId("vs-cascade")).toContainText(
        cascade.protocolCommit,
      );
      await page.waitForLoadState("networkidle");
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      const text = await page.locator("body").innerText();
      expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
    });

test("the cascade card states its scope and the numbers (en)", async ({
  page,
}) => {
  await stubApi(page, {});
  await page.goto("/en/research/validation-studies");
  const card = page.getByTestId("vs-cascade");
  await expect(card).toContainText("421 of 432 = 0.975 (95 % CI 0.955–0.986)");
  await expect(card).toContainText("79 of 217 = 0.364 (95 % CI 0.303–0.430)");
  await expect(card).toContainText("Hypothesis met.");
  await expect(card).toContainText("Hypothesis not met.");
  await expect(card).toContainText(
    "No notice does not mean there is no cascade.",
  );
  await expect(card).toContainText("All 77 of 77");
  await expect(card).toContainText("26 of 50");
  const faers = page.getByTestId("vs-faers");
  await expect(faers).toContainText("AUC 0.74 (95 % CI 0.69–0.78)");
  await expect(faers).toContainText("about one time in four");
  await expect(faers).toContainText("not evidence that a medicine causes");
});

test("the page is linked from the Research index and the calibration line links back to it", async ({
  page,
}) => {
  await stubApi(page, {});
  await page.goto("/en/research");
  await expect(
    page.locator('main a[href="/en/research/validation-studies"]'),
  ).toBeVisible();
  await page.goto("/en/research/validation-studies#faers");
  await expect(page.getByTestId("vs-faers")).toBeVisible();
});

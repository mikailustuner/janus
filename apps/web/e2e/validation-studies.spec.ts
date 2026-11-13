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
const VALIDATION = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "../src/research/validation.generated.json"),
    "utf8",
  ),
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
      for (const id of [
        "vs-cascade",
        "vs-faers",
        "vs-modelkit-precision",
        "vs-modelkit-gate",
      ]) {
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
      const { modelkitPrecision: mp, modelkitGate: mg } = VALIDATION;
      for (const [id, d] of [
        ["vs-modelkit-precision", mp],
        ["vs-modelkit-gate", mg],
      ] as const) {
        const links = main.getByTestId(id).getByRole("link");
        await expect(links.first()).toHaveAttribute("href", d.protocolUrl);
        await expect(links.last()).toHaveAttribute("href", d.resultsUrl);
        await expect(main.getByTestId(id)).toContainText(d.protocolCommit);
      }
      // Tables: real tables with a caption and column headers, rows from the generated file.
      const sources = main.getByTestId("vs-precision-sources");
      await expect(sources.locator("caption")).toHaveCount(1);
      await expect(sources.locator("thead th")).toHaveCount(6);
      await expect(sources.locator("tbody tr")).toHaveCount(mp.sources.length);
      await expect(main.getByTestId("vs-curve-row")).toHaveCount(
        mp.curve.length,
      );
      await expect(main.getByTestId("vs-gate-row")).toHaveCount(mg.rows.length);
      for (const r of mg.rows)
        await expect(
          main.locator(
            `[data-testid="vs-gate-row"][data-status="${r.status}"]`,
          ),
        ).not.toHaveCount(0);
      const fmt = (x: number, digits = 3) =>
        new Intl.NumberFormat(locale, {
          minimumFractionDigits: digits,
          maximumFractionDigits: digits,
        }).format(x);
      for (const s of mp.sources) {
        const row = main.getByTestId(`vs-precision-${s.key}`);
        await expect(row).toContainText(fmt(s.precision));
        await expect(row).toContainText(fmt(s.clusterLower));
      }
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
  // The shell streams in; look inside the real content, not the fallback copy.
  const card = page.locator("#content").getByTestId("vs-cascade");
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

test("the model kit cards state the numbers, the scope and the open items (en)", async ({
  page,
}) => {
  await stubApi(page, {});
  await page.goto("/en/research/validation-studies");
  const p = page.locator("#content").getByTestId("vs-modelkit-precision");
  await expect(p).toContainText("126 (14)");
  await expect(p).toContainText("0.992");
  await expect(p).toContainText("0.364");
  await expect(p.getByTestId("vs-precision-clinicaltrials_gov")).toContainText(
    "Passes",
  );
  await expect(p.getByTestId("vs-precision-pmc_oa")).toContainText("Held back");
  await expect(p).toContainText("Recall not yet measured");
  await expect(p).toContainText(
    "Two independent automated review passes. Expert review has not yet been done.",
  );
  const g = page.locator("#content").getByTestId("vs-modelkit-gate");
  await expect(g.getByTestId("vs-gate-result")).toContainText("needs 10 drugs");
  await expect(g.getByTestId("vs-gate-result")).toContainText("It has 0.");
  await expect(g.getByTestId("vs-gate-result")).toContainText(
    "upper bound with the current data is 0",
  );
  await expect(g).toContainText("Limited by the data");
  await expect(g.getByTestId("vs-gate-claim")).toContainText("11 of 11 points");
  await expect(g.getByTestId("vs-gate-cross")).toContainText(
    "did not meet its pre-registered decision rule, so it is switched off",
  );
  await expect(g.getByText("Shown by the data").first()).toBeVisible();
  await expect(g.getByText("Tested, not shown").first()).toBeVisible();
  await expect(g.getByText("Not tested yet").first()).toBeVisible();
});

test("the model kit page links to the model kit validation cards", async ({
  page,
}) => {
  await stubApi(page, {});
  await page.goto("/en/research/model-kit");
  const link = page.getByTestId("mk-validation-link");
  await expect(link).toHaveAttribute(
    "href",
    "/en/research/validation-studies#modelkit-precision",
  );
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

// Plan D3.2: every card saves its numbers as a CSV and shows the release citation.
test("each study downloads its CSV and shows the citation", async ({
  page,
}) => {
  await stubApi(page);
  await page.goto("/en/research/validation-studies");
  for (const card of [
    "cascade",
    "faers",
    "modelkitPrecision",
    "modelkitGate",
  ]) {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId(`vs-csv-${card}`).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(
      new RegExp(`^janus-${card}-v\\d+\\.\\d+\\.\\d+\\.csv$`),
    );
    const path = await download.path();
    const text = readFileSync(path, "utf8");
    expect(text.split("\r\n")[0]).toBe(
      "study,measure,k,n,estimate,ci95_low,ci95_high,cluster_lower,threshold,met",
    );
    expect(text).toContain(`\r\n${card},`);
  }
  await page.getByText("Cite this version").first().click();
  await expect(page.getByTestId("vs-cite-cascade")).toContainText(
    "Üstüner M. Janus",
  );
  await expect(page.getByTestId("vs-limitations")).toHaveAttribute(
    "href",
    /limitations\.md$/,
  );
});

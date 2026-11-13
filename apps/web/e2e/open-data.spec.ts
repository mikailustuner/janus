// Open data page (open-data Req 3; design §4): the API stubbed from synthetic answers
// (src/test/fixtures/open.ts), never from the recorded file; demo mode is checked for structure only. C1–C3 in five locales ×
// two themes; the honest empty state with no number; a released cell rendered as a table; the
// downloads; demo mode with no request; 503. Screenshots when OPEN_SHOTS_DIR is set.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { cell, openSet } from "../src/test/fixtures/open";

import {
  expectNoAxeViolations,
  expectNoHorizontalScroll,
  expectTouchTargets,
  LOCALES,
  recordRequests,
  stubApi,
  THEMES,
  useTheme,
} from "./helpers";

const read = (p: string) =>
  JSON.parse(readFileSync(join(import.meta.dirname, p), "utf8"));
const fx = openSet(); // no released cell: the empty state
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../messages/${l}.json`)]),
);
const SHOTS = process.env.OPEN_SHOTS_DIR;
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

for (const theme of THEMES)
  for (const locale of locales)
    test(`open data, ${locale}, ${theme}`, async ({ page }, info) => {
      await useTheme(page, theme);
      await stubApi(page, { "/open/outcomes": { body: fx.outcomes } });
      await page.goto(`/${locale}/open-data`);
      const m = messages[locale].OpenData;
      await expect(page.getByTestId("open-empty")).toHaveText(m.dataset.empty);
      await expect(page.getByTestId("open-notices")).toHaveText(m.rule.notices);
      await expect(page.getByTestId("disclaimer")).toHaveText(
        messages[locale].Disclaimer.text,
      );
      await page.waitForLoadState("networkidle");
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      const text = await page.locator("body").innerText();
      expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
      if (SHOTS && locale === "en") {
        mkdirSync(SHOTS, { recursive: true });
        await page.screenshot({
          path: join(SHOTS, `open-data-${info.project.name}-${theme}.png`),
          fullPage: true,
        });
      }
    });

test("empty state: no number for the dataset, no tile, the version and the licence", async ({
  page,
}) => {
  await stubApi(page, { "/open/outcomes": { body: fx.outcomes } });
  await page.goto("/en/open-data");
  const card = page.getByTestId("open-dataset");
  // The only number is the rule's threshold (20), not a count.
  expect(
    ((await card.innerText()).match(/\d+/g) ?? []).filter((n) => n !== "20"),
  ).toEqual([]);
  await expect(card.locator(".tile")).toHaveCount(0);
  await expect(page.getByTestId("open-cells")).toHaveCount(0);
  await expect(page.getByTestId("open-files")).toContainText(
    String(fx.outcomes.version),
  );
  await expect(page.getByTestId("open-files")).toContainText("CC BY 4.0");
  await expect(page.getByTestId("open-download-csv")).toHaveAttribute(
    "href",
    "/api/open/outcomes.csv",
  );
  await expect(page.getByTestId("open-package")).toContainText("pipc.csv");
  await expect(page.getByTestId("open-package")).toContainText("CC-BY-4.0");
  await expect(page.getByTestId("open-package")).not.toContainText(
    /TİTCK.*\.xlsx/,
  );
});

test("a released cell is shown as a row with names, never a hidden cell", async ({
  page,
}) => {
  const one = openSet([cell()]).outcomes;
  await stubApi(page, { "/open/outcomes": { body: one } });
  await page.goto("/en/open-data");
  const rows = page.getByTestId("open-cells").locator("tbody tr");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("amlodipine");
  await expect(rows.first()).toContainText("European Union");
  await expect(rows.first()).toContainText("23");
  await expect(page.getByTestId("open-empty")).toHaveCount(0);
  await expectNoHorizontalScroll(page);
});

test("states: 503 with retry", async ({ page }) => {
  await stubApi(page, {
    "/open/outcomes": { status: 503, body: { error: "open_data_unavailable" } },
  });
  await page.goto("/en/open-data");
  await expect(page.getByRole("alert").filter({ hasText: /\w/ })).toContainText(
    messages.en.OpenData.errors.unavailable,
  );
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("demo mode: the bundled file, downloads from it, no request", async ({
  page,
}) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  const requests = recordRequests(page);
  await page.goto("/en/open-data");
  await expect(page.getByTestId("open-demo")).toBeVisible();
  const href = await page.getByTestId("open-download-csv").getAttribute("href");
  expect(href).toMatch(/^data:text\/csv/);
  expect(decodeURIComponent(href!.split(",").slice(1).join(","))).toMatch(
    /^dataset_version,/,
  );
  expect(requests.filter((r) => r.url().includes("/api/"))).toEqual([]);
});

test("entry points: Research lists it and the footer links it", async ({
  page,
}) => {
  await page.goto("/en/research");
  await page
    .getByRole("link", { name: /Open data/ })
    .first()
    .click();
  await expect(page).toHaveURL(/\/en\/open-data$/);
  await expect(
    page.locator("footer").getByRole("link", { name: "Open data" }),
  ).toBeVisible();
});

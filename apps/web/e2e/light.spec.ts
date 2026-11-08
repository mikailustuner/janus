// Light face (light-face design §10, Req 4, 5.2, 5.3): the researcher screens with the API stubbed
// from answers recorded from the real build (src/light/fixture.recorded.json). C1–C3 in 5 locales ×
// 2 themes, the states, the rule-7 label, and screenshots at 375 and 1280 px in both themes.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { themeWords } from "../src/i18n/reassurance";

import {
  expectNoAxeViolations,
  expectNoHorizontalScroll,
  expectTouchTargets,
  LOCALES,
  stubApi,
  THEMES,
  useTheme,
} from "./helpers";

const fx = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "../src/light/fixture.recorded.json"),
    "utf8",
  ),
) as {
  overview: unknown;
  cards: Record<string, { goal: { key: string } }>;
  validation: unknown;
  export: unknown;
};
const seanceFx = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "../src/seance/fixture.recorded.json"),
    "utf8",
  ),
) as { catalogue: unknown };
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
const SHOTS = process.env.LIGHT_SHOTS_DIR;

async function stubLight(page: Page) {
  return stubApi(page, {
    "/light/overview": { body: fx.overview },
    "/light/cards": (body) => {
      const goal = (body as { goal?: string } | null)?.goal ?? "";
      const answer = fx.cards[goal];
      return answer
        ? { body: answer }
        : { status: 503, body: { error: "light_unavailable" } };
    },
    "/light/validation": { body: fx.validation },
    "/light/export": { body: fx.export },
    "/seance/catalogue": { body: seanceFx.catalogue },
  });
}

const ROUTES = [
  "/research",
  "/research/hypotheses",
  "/research/validation",
  "/research/export",
];
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

for (const theme of THEMES)
  for (const locale of locales)
    test(`light routes, ${locale}, ${theme}`, async ({ page }, info) => {
      await useTheme(page, theme);
      await stubLight(page);
      for (const route of ROUTES) {
        await page.goto(`/${locale}${route}`);
        await page.waitForLoadState("networkidle");
        await expect(page.getByTestId("disclaimer")).toHaveText(
          messages[locale].Disclaimer.text,
        );
        if (route !== "/research")
          await expect(page.getByTestId("rule7")).toHaveText(
            messages[locale].Light.rule7,
          );
        // the details of the first card are part of the checks
        const details = page.locator("details summary").first();
        if (await details.count()) await details.click();
        await expectNoAxeViolations(page);
        await expectNoHorizontalScroll(page);
        await expectTouchTargets(page);
        const text = await page.locator("body").innerText();
        expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual(
          [],
        );
        if (theme === "glass")
          expect(findForbiddenPhrases(text, themeWords[locale])).toEqual([]);
        if (SHOTS && locale === "en" && route !== "/research") {
          mkdirSync(SHOTS, { recursive: true });
          const name = route.split("/").pop();
          await page.screenshot({
            path: join(
              SHOTS,
              `light-${name}-${info.project.name}-${theme}.png`,
            ),
            fullPage: true,
          });
        }
      }
    });

test("hypotheses: picker, tied ranks, show more, sources", async ({ page }) => {
  await stubLight(page);
  await page.goto("/en/research/hypotheses");
  await expect(page.getByTestId("hypothesis-card").first()).toBeVisible();
  await expect(page.getByTestId("light-status")).toContainText(
    "Research prototype",
  );
  const alopecia = page.getByRole("radio", { name: /Hair loss/ });
  await alopecia.check();
  await expect(page.getByRole("article", { name: /minoxidil/i })).toBeVisible();
  await page.getByRole("radio", { name: /Erectile dysfunction/ }).check();
  await expect(
    page.getByRole("article", { name: /sildenafil/i }),
  ).toBeVisible();
  await page.getByRole("radio", { name: /Multiple myeloma/ }).check();
  await expect(
    page.getByText(/FAERS: reported less often than expected/).first(),
  ).toBeVisible();
});

test("hypotheses: error state with retry when the API is down", async ({
  page,
}) => {
  await stubApi(page, {
    "/light/overview": { status: 503, body: { error: "light_unavailable" } },
  });
  await page.goto("/en/research/hypotheses");
  await expect(page.getByRole("alert").filter({ hasText: /\w/ })).toContainText(
    messages.en.Light.errors.unavailable,
  );
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("validation: informative hits, chance level, every case", async ({
  page,
}) => {
  await stubLight(page);
  await page.goto("/en/research/validation");
  const summary = page.getByTestId("validation-summary");
  await expect(summary).toContainText("Primary run: 2 of 13 cases");
  await expect(page.getByTestId("validation-case")).toHaveCount(13);
  await expect(
    page.getByRole("article", { name: /thalidomide and Multiple myeloma/i }),
  ).toContainText("No side-effect term points to this condition");
});

test("export: licence and downloads", async ({ page }) => {
  await stubLight(page);
  await page.goto("/en/research/export");
  await expect(page.getByTestId("export-panel")).toContainText("CC BY 4.0");
  const [csv] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download CSV" }).click(),
  ]);
  expect(csv.suggestedFilename()).toMatch(/^janus-light-.*-cc-by-4\.0\.csv$/);
});

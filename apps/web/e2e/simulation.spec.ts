// Model explorer and queued model runs (simulation-service Req 1, 5; owner decision 2026-11-09).
// C1-C3 in five locales × two themes; the explorer runs on the device with no request, offers no
// person-specific input and shows only distributions, the validation status and the sentence; the
// server form goes queued → done (API stubbed from synthetic answers, src/test/fixtures/simulation.ts),
// 429 queue full, 503 off; demo mode (bundled recorded runs) with no request. Screenshots when RESEARCH_SHOTS_DIR is set.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { simulationSet } from "../src/test/fixtures/simulation";

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
const fx = simulationSet();
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../messages/${l}.json`)]),
);
const SHOTS = process.env.RESEARCH_SHOTS_DIR;
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

const done = fx.jobs[0]!.job;
const queued = {
  ...done,
  state: "queued",
  queue_position: 2,
  result: null,
  cached: false,
};
const serverStubs = {
  "/simulate/compounds": { body: fx.compounds },
  "/simulate": { status: 202, body: queued },
  [`/simulate/jobs/${done.job_id}`]: { body: done },
};

async function checks(page: Page, locale: (typeof LOCALES)[number]) {
  await expect(page.getByTestId("disclaimer")).toHaveText(
    messages[locale].Disclaimer.text,
  );
  await page.waitForLoadState("networkidle");
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  const text = await page.locator("body").innerText();
  expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
}

async function shot(page: Page, name: string, project: string, theme: string) {
  if (!SHOTS) return;
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({
    path: join(SHOTS, `research-${name}-${project}-${theme}.png`),
    fullPage: true,
  });
}

for (const theme of THEMES)
  for (const locale of locales) {
    test(`model explorer, ${locale}, ${theme}`, async ({ page }, info) => {
      await useTheme(page, theme);
      const requests = recordRequests(page);
      await page.goto(`/${locale}/research/model-explorer`);
      const main = page.getByRole("main");
      await expect(main.getByTestId("explorer-result")).toBeVisible();
      await expect(
        main.getByTestId("explorer-result-disclaimer"),
      ).toContainText(messages[locale].Simulation.virtualPopulation);
      await expect(main.getByTestId("sim-validation")).toBeVisible();
      await checks(page, locale);
      // No input asks for anything personal: the only free inputs are the dose and the number of
      // doses; everything else is a choice among predefined options.
      const free = main
        .getByTestId("explorer-form")
        .locator("input:not([type=radio]), select, textarea");
      expect(
        await free.evaluateAll((els) =>
          els.map((e) => e.getAttribute("data-testid")),
        ),
      ).toEqual(["explorer-dose", "explorer-doses"]);
      expect(requests.filter((r) => r.url().includes("/api/"))).toEqual([]);
      if (locale === "en")
        await shot(page, "model-explorer", info.project.name, theme);
    });

    test(`queued runs, ${locale}, ${theme}`, async ({ page }, info) => {
      await useTheme(page, theme);
      await stubApi(page, serverStubs);
      await page.goto(`/${locale}/research/simulate`);
      const main = page.getByRole("main");
      await main.getByTestId("sim-submit").click();
      await expect(main.getByTestId("sim-status")).toHaveAttribute(
        "data-state",
        "queued",
      );
      await expect(main.getByTestId("sim-result")).toBeVisible({
        timeout: 10_000,
      });
      await expect(main.getByTestId("sim-result-disclaimer")).toContainText(
        messages[locale].Simulation.virtualPopulation,
      );
      await expect(main.getByTestId("sim-chart")).toBeVisible();
      await checks(page, locale);
      if (locale === "en")
        await shot(page, "simulate", info.project.name, theme);
    });
  }

test("explorer: a dose outside the bounds runs nothing; a schedule runs", async ({
  page,
}) => {
  await page.goto("/en/research/model-explorer");
  const main = page.getByRole("main");
  await page.waitForLoadState("networkidle");
  await expect(main.getByTestId("explorer-result")).toBeVisible();
  await main.getByTestId("explorer-dose").fill("50");
  await expect(main.getByTestId("explorer-invalid")).toBeVisible();
  await expect(main.getByTestId("explorer-result")).toHaveCount(0);
  await main.getByTestId("explorer-dose").fill("5");
  await main.getByTestId("explorer-doses").fill("7");
  await expect(main.getByRole("radio", { name: "every 24 h" })).toBeChecked();
  await expect(main.getByTestId("explorer-extrapolation")).toBeVisible();
  await expect(main.getByTestId("explorer-result")).toBeVisible();
  await expect(main.getByText("Simulated time: 192 hours.")).toBeVisible();
  // 14 doses every 24 h fit the simulated time exactly (360 h); nothing is cut short.
  await main.getByTestId("explorer-doses").fill("14");
  await expect(main.getByText("Simulated time: 360 hours.")).toBeVisible();
  // Rhein has no older-adult population (no verified data).
  await main.getByRole("radio", { name: "rhein" }).check();
  await expect(main.getByRole("radio", { name: /Older adults/ })).toHaveCount(
    0,
  );
  await expect(main.getByTestId("explorer-canon-note")).toBeVisible();
  await expect(main.getByTestId("sim-validation")).toHaveAttribute(
    "data-credibility",
    "credible",
  );
});

test("queued runs: queue full and switched off", async ({ page }) => {
  await stubApi(page, {
    "/simulate/compounds": { body: fx.compounds },
    "/simulate": {
      status: 429,
      body: { error: "queue_full", disclaimer: "x" },
    },
  });
  await page.goto("/en/research/simulate");
  await page.getByRole("main").getByTestId("sim-submit").click();
  await expect(page.getByRole("alert").filter({ hasText: /\w/ })).toContainText(
    messages.en.Simulation.errors.queueFull,
  );
  await stubApi(page, {
    "/simulate/compounds": { body: { ...fx.compounds, server_runs: false } },
  });
  await page.goto("/en/research/simulate");
  await expect(page.getByText(messages.en.Simulation.server.off)).toBeVisible();
});

test("demo mode: the recorded runs, no request", async ({ page }) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  const requests = recordRequests(page);
  await page.goto("/en/research/simulate");
  await expect(page.getByTestId("sim-demo")).toBeVisible();
  await page.getByRole("main").getByTestId("sim-submit").click();
  await expect(page.getByRole("main").getByTestId("sim-result")).toBeVisible();
  await page
    .getByRole("main")
    .getByRole("radio", { name: "httk population" })
    .check();
  await page.getByRole("main").getByTestId("sim-submit").click();
  await expect(page.getByRole("main").getByTestId("sim-ratio")).toBeVisible();
  expect(requests.filter((r) => r.url().includes("/api/"))).toEqual([]);
});

test("entry points: Research lists both", async ({ page }) => {
  for (const [name, url] of [
    [
      messages.en.Research.tools.modelExplorer.title,
      /research\/model-explorer$/,
    ],
    [messages.en.Research.tools.simulate.title, /research\/simulate$/],
  ] as const) {
    await page.goto("/en/research");
    await page
      .getByRole("link", { name: new RegExp(name) })
      .first()
      .click();
    await expect(page).toHaveURL(url);
  }
});

// Safety check (safety-check Req 7): "More checks on this list" on the results screen. The API
// is stubbed with the answer the API tests produce (src/safety/fixtures/check.json; invented
// products). C1-C3 in five locales × two themes; the request is the evaluation's own body and
// carries no box name; nothing found, loading, error with retry, demo mode with no request.
// Screenshots when SAFETY_SHOTS_DIR is set.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { reassurance } from "../src/i18n/reassurance";

import {
  expectNoAxeViolations,
  expectNoHorizontalScroll,
  expectTouchTargets,
  LOCALES,
  stubApi,
  THEMES,
  useTheme,
} from "./helpers";

const read = (p: string) =>
  JSON.parse(readFileSync(join(import.meta.dirname, p), "utf8"));
const sample = read("../src/safety/fixtures/check.json");
const none = {
  ...sample,
  not_checked: [],
  duplication: {
    ...sample.duplication,
    findings: [],
    statement: { code: "no_duplication_found", text: "canonical" },
  },
};
const fx = read("../src/demo/fixtures/istanbul.json");
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../messages/${l}.json`)]),
);
const SHOTS = process.env.SAFETY_SHOTS_DIR;
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

// The Istanbul demo products as a person's own list, with long hand-typed box names.
const listDoc = {
  v: 1,
  items: fx.items.map(
    (
      it: {
        resolution: { dataset_version: string; candidates: unknown[] };
        sourceKey: unknown;
        boxName: string;
        started: string | null;
      },
      i: number,
    ) => ({
      id: `x${i}`,
      sourceKey: it.sourceKey,
      datasetVersion: it.resolution.dataset_version,
      candidate: it.resolution.candidates[0],
      choices: [],
      started: it.started,
      boxName: `ZZBOX${i} ${it.boxName} Langwortzusammensetzungsbeispiel`,
      needsConfirmation: false,
    }),
  ),
};
const seed = (page: Page) =>
  page.addInitScript(
    (doc) => localStorage.setItem("janus.v1.list", JSON.stringify(doc)),
    listDoc,
  );
const bodies = (
  seen: { url(): string; postDataJSON(): unknown }[],
  path: string,
) => seen.filter((r) => r.url().endsWith(path)).map((r) => r.postDataJSON());
const plural = (message: string, count: number) =>
  message
    .replace(
      /\{count, plural, one \{([^}]*)\} other \{([^}]*)\}\}/,
      (_, one, other) => (count === 1 ? one : other),
    )
    .replace(/#/g, String(count));

async function shot(page: Page, name: string, project: string) {
  if (!SHOTS) return;
  mkdirSync(SHOTS, { recursive: true });
  await page
    .getByTestId("safety-checks")
    .screenshot({ path: join(SHOTS, `${name}-${project}.png`) });
}

for (const locale of locales)
  for (const theme of THEMES)
    test(`results: findings of the further checks, ${locale}, ${theme}`, async ({
      page,
    }, info) => {
      const m = messages[locale].SafetyCheck;
      await useTheme(page, theme);
      await seed(page);
      const seen = await stubApi(page, {
        "/cascades/evaluate": { body: fx.evaluation },
        "/safety/check": { body: sample },
      });
      await page.goto(`/${locale}/results`);
      const section = page.getByTestId("safety-checks");
      await expect(
        section.getByRole("heading", { level: 2 }).first(),
      ).toHaveText(m.title);
      const findings = section.getByTestId("dup-finding");
      await expect(findings).toHaveCount(3);
      // The medicines are named by the person's own box names; the group by its ATC code.
      await expect(findings.nth(0)).toHaveAttribute(
        "data-kind",
        "same_ingredient",
      );
      for (const i of [0, 1, 4])
        await expect(findings.nth(0)).toContainText(`ZZBOX${i} `);
      await expect(findings.nth(2)).toHaveAttribute("data-kind", "same_group");
      await expect(findings.nth(2)).toContainText("C09AA");
      await expect(findings.nth(2)).toContainText(m.dup.unconfirmed);
      await expect(section).toContainText(m.dup.advice);
      await expect(section).toContainText(m.review);
      await expect(section).toContainText(m.dup.method);
      await expect(section.getByTestId("safety-sources")).toContainText(
        "2026-11-06",
      );
      await expect(section.getByTestId("safety-not-checked")).toHaveText(
        plural(m.notChecked, 1),
      );
      // One request, with the body of the evaluation and no box name.
      const sent = bodies(seen, "/api/safety/check");
      expect(sent).toEqual(bodies(seen, "/api/cascades/evaluate"));
      expect(sent).toHaveLength(1);
      expect(JSON.stringify(sent)).not.toContain("ZZBOX");
      const text = (await section.innerText()).replace(/\s+/g, " ");
      expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
      expect(findForbiddenPhrases(text, reassurance[locale])).toEqual([]);
      // Not an alert: no warning or emergency colour inside the section.
      expect(
        await section.locator('[class*="-risk"], [class*="-warn"]').count(),
      ).toBe(0);
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      await shot(page, `findings-${locale}-${theme}`, info.project.name);
    });

for (const locale of locales)
  test(`nothing found is not a clearance, ${locale}`, async ({
    page,
  }, info) => {
    const m = messages[locale].SafetyCheck;
    await seed(page);
    await stubApi(page, {
      "/cascades/evaluate": { body: fx.evaluation },
      "/safety/check": { body: none },
    });
    await page.goto(`/${locale}/results`);
    const section = page.getByTestId("safety-checks");
    await expect(section.getByTestId("dup-none")).toContainText(
      plural(m.dup.none, sample.ingredients_checked),
    );
    await expect(section.getByTestId("dup-finding")).toHaveCount(0);
    await expect(section).not.toContainText(m.dup.advice);
    await section.getByText(m.about).first().click();
    await expect(section).toContainText(m.dup.method);
    await expectNoAxeViolations(page);
    await expectNoHorizontalScroll(page);
    await shot(page, `none-${locale}`, info.project.name);
  });

test("loading, then an error with a retry, then the answer", async ({
  page,
}, info) => {
  await seed(page);
  let calls = 0;
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  await stubApi(page, { "/cascades/evaluate": { body: fx.evaluation } });
  await page.route("**/api/safety/check", async (route) => {
    calls += 1;
    if (calls === 1) await gate;
    await route.fulfill({
      status: calls === 1 ? 503 : 200,
      contentType: "application/json",
      body: JSON.stringify(
        calls === 1 ? { error: "safety_unavailable" } : sample,
      ),
    });
  });
  await page.goto("/en/results");
  await expect(page.getByTestId("safety-loading")).toHaveText(
    "Comparing the medicines on your list…",
  );
  // The cascade findings do not wait for the further checks.
  await expect(page.getByTestId("finding").first()).toBeVisible();
  release();
  const error = page.getByTestId("safety-error");
  await expect(error).toContainText(
    "Janus could not run these checks. These checks are not available right now. Please try again later.",
  );
  await expect(page.getByTestId("dup-finding")).toHaveCount(0);
  await expect(page.getByTestId("dup-none")).toHaveCount(0);
  await expectNoAxeViolations(page);
  await shot(page, "error", info.project.name);
  await error.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByTestId("dup-finding")).toHaveCount(3);
  expect(calls).toBe(2);
});

test("demo mode: no request, one line that says so", async ({ page }) => {
  const seen = await stubApi(page);
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  await page.goto("/en/results");
  await expect(page.getByTestId("safety-demo")).toHaveText(
    "The further checks of the list (same ingredient, label text, anticholinergic scales) do not run in the demo.",
  );
  await expect(page.getByTestId("safety-checks")).toHaveCount(0);
  expect(bodies(seen, "/api/safety/check")).toEqual([]);
});

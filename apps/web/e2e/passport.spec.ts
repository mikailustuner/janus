// medication-passport task 12: the Passport screens in a real browser. Axe (WCAG 2.2 A/AA), no
// horizontal scroll, 44 px targets and the disclaimer at 375 px and 1280 px (by project) in both
// themes; the Cologne demo (recorded answer, no request to the API, demo label on both screens);
// the live states with a stubbed API (loaded, error with retry); screenshots for the review.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  expectNoAxeViolations,
  expectNoHorizontalScroll,
  expectTouchTargets,
  recordRequests,
  stubApi,
  THEMES,
  useTheme,
} from "./helpers";

const SHOTS = process.env.PASSPORT_SHOTS;
const recorded = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "../src/demo/passport-istanbul.recorded.json"),
    "utf8",
  ),
);
const istanbul = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "../src/demo/fixtures/istanbul.json"),
    "utf8",
  ),
);

async function checks(page: Page) {
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, {
    timeout: 15_000,
  });
  await expect(page.getByTestId("disclaimer")).toBeVisible();
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
}

async function shot(page: Page, name: string, project: string) {
  if (!SHOTS) return;
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({
    path: join(SHOTS, `passport-${name}-${project}.png`),
    fullPage: true,
  });
}

for (const theme of THEMES) {
  test(`Cologne demo, list and detail, ${theme}`, async ({ page }, info) => {
    await useTheme(page, theme);
    await page.addInitScript(() =>
      sessionStorage.setItem("janus.v1.demo", "cologne"),
    );
    const requests = recordRequests(page);
    await page.goto("/en/passport");
    await checks(page);
    await expect(page.getByTestId("demo-label")).toBeVisible();
    await expect(
      page.getByText("Same active ingredient under different names:"),
    ).toHaveCount(2);
    await expect(
      page.getByText("Homeopathic product, not checked."),
    ).toBeVisible();
    await shot(page, `list-${theme}`, info.project.name);

    await page.goto("/en/passport/item#demo-cologne-passport-5");
    await checks(page);
    await expect(page.getByTestId("demo-label")).toBeVisible();
    await expect(
      page.getByText(/^Recorded answer of \d{4}-\d{2}-\d{2}\.$/),
    ).toBeVisible();
    await expect(
      page
        .getByRole("status")
        .filter({ hasText: "Results for 4 sources loaded." }),
    ).toHaveCount(1);
    await expect(
      page.getByText("as entered from the box").first(),
    ).toBeVisible();
    await expect(
      page.getByText("Janus shows listings in public data only.").first(),
    ).toBeVisible();
    await shot(page, `detail-${theme}`, info.project.name);

    expect(
      requests
        .filter((r) => new URL(r.url()).pathname.startsWith("/api/"))
        .map((r) => r.url()),
    ).toEqual([]);
  });
}

/** A stored list with one Turkish box from the Istanbul fixture (the person's own list). */
async function ownList(page: Page) {
  const it = istanbul.items[2];
  const res = it.resolution;
  await page.addInitScript(
    (item) =>
      localStorage.setItem(
        "janus.v1.list",
        JSON.stringify({ v: 1, items: [item] }),
      ),
    {
      id: "own-1",
      sourceKey: it.sourceKey,
      datasetVersion: res.dataset_version,
      candidate: res.candidates[0],
      choices: it.choices,
      started: it.started,
      boxName: "Own box 1000",
      needsConfirmation: false,
    },
  );
  return it;
}

test("own list: live answer, typed strength sent as a code only", async ({
  page,
}) => {
  await ownList(page);
  const bodies: unknown[] = [];
  const key = recorded.request.items.find(
    (q: { ingredients: { key: string }[] }) =>
      q.ingredients[0]!.key === "Q19484",
  );
  await stubApi(page, {
    "/passport/presence": (body) => {
      bodies.push(body);
      const out = structuredClone(recorded.response);
      const i = recorded.request.items.indexOf(key);
      out.items = [
        { ...out.items.find((x: { item: number }) => x.item === i), item: 0 },
      ];
      return { body: out };
    },
  });
  await page.goto("/en/passport/item#own-1");
  await checks(page);
  await expect(
    page.getByRole("status").filter({ hasText: "sources loaded" }),
  ).toHaveCount(1);
  await page
    .getByRole("button", { name: "Add strength and form from the box" })
    .click();
  await page.getByLabel("Amount").fill("1,000");
  await page.getByRole("button", { name: "Use these values" }).click();
  await expect(page.locator("#content").getByRole("alert")).toContainText(
    "without thousands separators",
  );
  await page.getByLabel("Amount").fill("1000");
  await page.getByRole("button", { name: "Use these values" }).click();
  await expect(page.getByText(/This box: 1,000 mg per tablet/)).toBeVisible();
  await expect.poll(() => bodies.length).toBeGreaterThanOrEqual(2);
  const text = JSON.stringify(bodies);
  expect(text).not.toContain("Own box");
  expect(text).not.toContain("own-1");
  expect(text).toContain('"amount":"1000000"');
});

test("own list: 503 shows the error with a retry, never 'not found'", async ({
  page,
}) => {
  await ownList(page);
  let calls = 0;
  await stubApi(page, {
    "/passport/presence": () => {
      calls++;
      return { status: 503, body: { error: "passport_unavailable" } };
    },
  });
  await page.goto("/en/passport/item#own-1");
  await expect(page.locator("#content").getByRole("alert")).toContainText(
    "These listings could not be checked now.",
  );
  await expect(page.locator("body")).not.toContainText(/not found/i);
  await page.getByRole("button", { name: "Try again" }).click();
  await expect.poll(() => calls).toBeGreaterThanOrEqual(2);
  await expectNoAxeViolations(page);
});

test("medicines link to the passport, keyboard reachable", async ({ page }) => {
  await ownList(page);
  await stubApi(page, {});
  await page.goto("/en/medicines");
  const link = page.getByRole("link", {
    name: /Show this box in the passport/,
  });
  await expect(link).toBeVisible();
  await link.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/en\/passport\/item#own-1$/);
});

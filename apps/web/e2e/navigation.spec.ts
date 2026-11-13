// Plan D1: two ways in from the home, a patient menu and a researcher menu that never mix, the
// experimental pages only in the researcher area with their label, and keyboard reach of both
// menus. Runs at both viewports (phone: bottom bar; desktop: header).
import { expect, test, type Page } from "@playwright/test";

import { expectNoAxeViolations, stubApi } from "./helpers";

const EXPERIMENTAL = [
  "/research/hypotheses",
  "/research/seance",
  "/research/time-machine",
];

/** The visible menu at this viewport: the bottom bar on a phone, the header on a desktop. */
function menu(page: Page) {
  return page
    .locator('[data-testid="bottom-nav"], [data-testid="header-nav"]')
    .filter({ visible: true });
}

async function menuHrefs(page: Page): Promise<string[]> {
  const links = menu(page).getByRole("link");
  await expect(links).toHaveCount(5);
  return links.evaluateAll((els) =>
    els.map((a) => new URL((a as HTMLAnchorElement).href).pathname),
  );
}

test("the home offers the two ways in", async ({ page }) => {
  await stubApi(page);
  await page.goto("/en");
  // The shell streams in; look inside the real content, not the fallback copy.
  const content = page.locator("#content");
  const entries = content.getByTestId("audience-entries");
  await expect(entries).toBeVisible();
  await expect(content.getByTestId("audience-patients")).toHaveAttribute(
    "href",
    "/en/scan",
  );
  await expect(content.getByTestId("audience-researchers")).toHaveAttribute(
    "href",
    "/en/research",
  );
  await content.getByTestId("audience-researchers").click();
  await expect(page).toHaveURL(/\/en\/research$/);
});

test("patient pages show the patient menu only", async ({ page }) => {
  await stubApi(page);
  await page.goto("/en/medicines");
  expect(await menuHrefs(page)).toEqual([
    "/en/scan",
    "/en/medicines",
    "/en/results",
    "/en/note",
    "/en/passport",
  ]);
  await expect(
    menu(page).getByRole("link", { name: "Medicines" }),
  ).toHaveAttribute("aria-current", "page");
  // Settings stays one tap away, from the header.
  await expect(page.getByTestId("settings-link")).toBeVisible();
  // No experimental page is linked from the patient menu or the header.
  for (const href of EXPERIMENTAL) {
    await expect(
      page.locator(`header a[href^="/en${href}"], nav a[href^="/en${href}"]`),
    ).toHaveCount(0);
  }
});

test("researcher pages show the researcher menu and the way back", async ({
  page,
}) => {
  await stubApi(page);
  await page.goto("/en/research/validation-studies");
  expect(await menuHrefs(page)).toEqual([
    "/en/research",
    "/en/research/validation-studies",
    "/en/research/model-kit",
    "/en/open-data",
    "/en/research/developers",
  ]);
  await expect(
    menu(page).getByRole("link", { name: "Validation" }),
  ).toHaveAttribute("aria-current", "page");
  const back = page.getByTestId("section-switch");
  await expect(back).toHaveText("Patient section");
  await back.click();
  await expect(page).toHaveURL(/\/en$/);
});

test("the hub groups its entries and labels the experimental ones", async ({
  page,
}) => {
  await stubApi(page);
  await page.goto("/en/research");
  for (const g of [
    "methods",
    "modelKit",
    "data",
    "developers",
    "experimental",
  ]) {
    await expect(page.getByTestId(`research-group-${g}`)).toBeVisible();
  }
  const experimental = page.getByTestId("research-group-experimental");
  await expect(experimental.getByRole("heading")).toContainText("Experimental");
  for (const href of EXPERIMENTAL) {
    await expect(experimental.locator(`a[href="/en${href}"]`)).toHaveCount(1);
  }
  await expectNoAxeViolations(page);
});

test("both menus are reachable by keyboard", async ({ page }) => {
  await stubApi(page);
  for (const path of ["/en/medicines", "/en/research"]) {
    await page.goto(path);
    const first = menu(page).getByRole("link").first();
    await expect(first).toBeVisible();
    // Tab through the page until the menu's first link has the focus (bounded).
    let reached = false;
    for (let i = 0; i < 80 && !reached; i++) {
      await page.keyboard.press("Tab");
      reached = await first.evaluate((el) => el === document.activeElement);
    }
    expect(reached, path).toBe(true);
  }
});

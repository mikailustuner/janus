// Plan D2.5: every patient screen on an empty device, with the API failing (HTTP error) and with
// the API unreachable (network failure): the screen still has its heading and readable content,
// no script error, no "undefined"/"NaN" in the text and no horizontal scroll.
import { expect, test, type Page } from "@playwright/test";

import { expectNoHorizontalScroll } from "./helpers";

const PATIENT = [
  "/scan",
  "/medicines",
  "/medicines/info",
  "/results",
  "/results/summary",
  "/results/finding",
  "/note",
  "/note/withdraw",
  "/passport",
  "/passport/products",
  "/passport/item",
  "/timeline",
  "/memory",
  "/settings",
  "/start",
  "/report",
  "/confirm",
  "/donate",
  "/donate/delete",
];

const MODES = {
  "API error": (page: Page) =>
    page.route("**/api/**", (r) =>
      r.fulfill({ status: 503, body: '{"error":"unavailable"}' }),
    ),
  "API unreachable": (page: Page) =>
    page.route("**/api/**", (r) => r.abort("internetdisconnected")),
} as const;

for (const [mode, setup] of Object.entries(MODES)) {
  for (const path of PATIENT) {
    test(`${path} on an empty device, ${mode}`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await setup(page);
      await page.goto(`/en${path}`);
      const main = page.locator("#content");
      await expect(main.locator("h1").first()).toBeVisible();
      // Let any request settle into its loaded, empty or error state.
      await page.waitForLoadState("networkidle");
      const text = (await main.innerText()).trim();
      expect(text.length, "readable content").toBeGreaterThan(20);
      expect(text).not.toMatch(/\bundefined\b|\bNaN\b|\[object Object\]/);
      // No raw message keys (a missing translation shows its key path).
      expect(text).not.toMatch(/\b[A-Z][A-Za-z]+\.[a-z][A-Za-z]+\.[a-z]/);
      await expectNoHorizontalScroll(page);
      expect(errors, errors.join("\n")).toEqual([]);
    });
  }
}

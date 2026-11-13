// Plan D5.2: keyboard and focus. On patient and researcher pages: the skip link moves focus to the
// content; every focused control shows a visible focus indicator (WCAG 2.4.7) and is not hidden
// behind the fixed header or bottom bar (WCAG 2.2, 2.4.11); no positive tabindex; heading levels
// never skip; disclosures open from the keyboard.
import { expect, test, type Page } from "@playwright/test";

import { stubApi } from "./helpers";

const PAGES = [
  "/en",
  "/en/scan",
  "/en/medicines",
  "/en/passport",
  "/en/settings",
  "/en/privacy",
  "/en/research",
  "/en/research/validation-studies",
  "/en/research/for-researchers",
];

async function open(page: Page, path: string) {
  await stubApi(page);
  await page.goto(path);
  await expect(page.locator("#content h1").first()).toBeVisible();
}

test("the skip link moves focus to the content", async ({ page }) => {
  await open(page, "/en/medicines");
  await page.keyboard.press("Tab");
  const skip = page.locator('a[href="#content"]');
  await expect(skip).toBeFocused();
  await expect(skip).toBeVisible();
  await page.keyboard.press("Enter");
  await expect
    .poll(() => page.evaluate(() => document.activeElement?.id))
    .toBe("content");
});

for (const path of PAGES) {
  test(`${path}: focus is visible and not obscured, no positive tabindex`, async ({
    page,
  }) => {
    await open(page, path);
    expect(
      await page
        .locator("[tabindex]:not([tabindex='0']):not([tabindex='-1'])")
        .count(),
    ).toBe(0);
    const problems: string[] = [];
    let previous = "";
    for (let i = 0; i < 60; i++) {
      await page.keyboard.press("Tab");
      const info = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el || el === document.body) return null;
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        const ring =
          (cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) >= 2) ||
          (cs.boxShadow !== "none" && cs.boxShadow !== "");
        // Fixed bars that could cover the focused control (the bottom bar, the app header).
        const covered = [
          ...document.querySelectorAll<HTMLElement>(
            '[data-testid="bottom-nav"], header.app-header',
          ),
        ]
          .filter(
            (bar) =>
              !bar.contains(el) && getComputedStyle(bar).position === "fixed",
          )
          .some((bar) => {
            const b = bar.getBoundingClientRect();
            if (b.height === 0) return false;
            const top = Math.max(r.top, b.top);
            const bottom = Math.min(r.bottom, b.bottom);
            // Entirely hidden (2.4.11 minimum): the overlap covers the whole control.
            return bottom - top >= r.height - 1 && r.height > 0;
          });
        const label =
          el.getAttribute("aria-label") ||
          el.textContent?.trim().slice(0, 40) ||
          el.tagName;
        return { label, ring, covered, key: `${el.tagName}:${label}:${r.top}` };
      });
      if (!info) continue;
      if (info.key === previous) break;
      previous = info.key;
      if (!info.ring) problems.push(`no visible focus: ${info.label}`);
      if (info.covered)
        problems.push(`hidden behind a fixed bar: ${info.label}`);
    }
    expect(problems).toEqual([]);
  });

  test(`${path}: heading levels never skip`, async ({ page }) => {
    await open(page, path);
    const levels = await page
      .locator("#content")
      .evaluate((main) =>
        [...main.querySelectorAll("h1, h2, h3, h4, h5, h6")]
          .filter((h) => (h as HTMLElement).offsetParent !== null)
          .map((h) => Number(h.tagName[1])),
      );
    expect(levels[0]).toBe(1);
    const jumps = levels.filter((l, i) => i > 0 && l > levels[i - 1]! + 1);
    expect(jumps, levels.join(",")).toEqual([]);
  });
}

test("a disclosure opens and closes from the keyboard", async ({ page }) => {
  await open(page, "/en/research/validation-studies");
  const summary = page
    .locator("#content summary", { hasText: "Cite this version" })
    .first();
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("vs-cite-cascade")).toBeVisible();
  await page.keyboard.press("Space");
  await expect(page.getByTestId("vs-cite-cascade")).toBeHidden();
});

test("the language can be changed from the keyboard", async ({ page }) => {
  await open(page, "/en/medicines");
  const select = page.locator("header select").first();
  await select.focus();
  await select.selectOption("tr");
  await expect(page).toHaveURL(/\/tr\/medicines/);
});

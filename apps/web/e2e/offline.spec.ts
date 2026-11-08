// Task 20: after one visit the Istanbul demo works with the network offline (20.1); /api is never
// cached; C7: reduced motion stops the ghost drift, reduce transparency gives solid cards; large
// text at 375 px without horizontal scroll (20.2).
import { expect, test } from "@playwright/test";

import { expectNoHorizontalScroll } from "./helpers";

test("the demo works offline after one visit, and /api is never cached", async ({
  page,
  context,
}) => {
  await page.goto("/en");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload(); // controlled by the service worker from here on
  await page.getByRole("link", { name: "Try the demo" }).click();
  await page.getByRole("button", { name: "Open the Istanbul patient" }).click();
  await page.getByRole("link", { name: "Check for patterns" }).click();
  await expect(
    page.locator('[data-testid="finding"][data-rule="pipc:5"]'),
  ).toBeVisible();
  await page.goto("/en/results/finding#1");
  await expect(page.getByTestId("pair-panel")).toBeVisible();
  await page.goto("/en/note");
  await expect(
    page.getByRole("button", { name: "Make the note" }),
  ).toBeVisible();

  await context.setOffline(true);
  await page.goto("/en/results");
  await expect(
    page.locator('[data-testid="finding"][data-rule="pipc:5"]'),
  ).toBeVisible();
  await page.goto("/en/results/finding#1");
  await expect(page.getByTestId("pair-panel")).toBeVisible();
  await page.goto("/en/note");
  await page.getByRole("button", { name: "Make the note" }).click();
  await expect(page.getByTestId("note-paper")).toBeVisible();
  await context.setOffline(false);

  const cached = await page.evaluate(async () => {
    const urls: string[] = [];
    for (const name of await caches.keys())
      for (const req of await (await caches.open(name)).keys())
        urls.push(new URL(req.url).pathname);
    return urls;
  });
  expect(cached.length).toBeGreaterThan(10);
  expect(cached.filter((u) => u.startsWith("/api/"))).toEqual([]);
});

test("C7: reduced motion stops the ghost drift", async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const page = await context.newPage();
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  await page.goto("/en/results");
  const ghost = page.locator('[data-testid="finding"] .ghost-body').first();
  await expect(ghost).toBeVisible();
  expect(await ghost.evaluate((el) => getComputedStyle(el).animationName)).toBe(
    "none",
  );
  expect(
    await page.evaluate(
      () => getComputedStyle(document.documentElement).transitionDuration,
    ),
  ).toBe("0s");
  await context.close();
});

test("C7: reduce transparency gives solid cards in Glass", async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem(
      "janus.v1.settings",
      JSON.stringify({ v: 1, theme: "glass", reduceTransparency: true }),
    ),
  );
  await page.goto("/en/demo");
  const card = page.locator(".card").first();
  const style = await card.evaluate((el) => ({
    bg: getComputedStyle(el).backgroundColor,
    blur: getComputedStyle(el).backdropFilter,
  }));
  expect(style.bg).toMatch(/rgb\(255, 255, 255\)|rgb\(28, 31, 34\)/);
  expect(style.blur).toBe("none");
});

test("large text at 375 px: 19 px base, no horizontal scroll", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "phone", "phone profile only");
  await page.addInitScript(() => {
    localStorage.setItem(
      "janus.v1.settings",
      JSON.stringify({ v: 1, largeText: true }),
    );
    sessionStorage.setItem("janus.v1.demo", "istanbul");
  });
  for (const path of [
    "/de",
    "/de/results",
    "/de/memory",
    "/de/note",
    "/de/settings",
    "/de/privacy",
  ]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    expect(
      await page.evaluate(
        () => getComputedStyle(document.documentElement).fontSize,
      ),
    ).toBe("19px");
    await expectNoHorizontalScroll(page);
  }
});

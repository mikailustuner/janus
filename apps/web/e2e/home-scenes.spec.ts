// Home scenes (experience Req 27.6–27.9, DP46, DP49): "Step inside" plays the door video once
// and lands in scene 3, where the Night Pharmacy findings are real buttons into the demo; reduced
// motion and Save-Data go straight to scene 3 and never request the video; each theme loads only
// its own hero image; the LCP is measured and recorded.
import { expect, test, type Page } from "@playwright/test";

import { recordRequests, useTheme } from "./helpers";

const video = (url: string) => /\/home\/door-\d+\.(mp4|webm)$/.test(url);
const hero = (page: Page) => page.locator("#content").getByTestId("night-hero");
const roomTitle = (page: Page) =>
  hero(page).getByRole("heading", {
    level: 2,
    name: "Four ghosts in a demo medicine cabinet",
  });

test("Night Pharmacy: step inside, skip, and the ghosts open the Istanbul demo findings", async ({
  page,
}) => {
  await page.goto("/en", { waitUntil: "networkidle" });
  // Keyboard order: hero actions first, then step inside; the findings come after it.
  const order = await page.evaluate(() =>
    [
      ...document.querySelectorAll<HTMLElement>(
        "#content .np a, #content .np button:not([tabindex='-1'])",
      ),
    ].map((e) => e.textContent?.trim() ?? ""),
  );
  expect(order.slice(0, 3)).toEqual([
    "Try the demo",
    "How it works",
    "Step inside",
  ]);
  // Nothing on the home is pinned or driven by scroll.
  expect(
    await page.evaluate(
      () =>
        [...document.querySelectorAll("#content *")].filter(
          (e) => getComputedStyle(e).position === "sticky",
        ).length,
    ),
  ).toBe(0);
  await hero(page).getByRole("button", { name: "Step inside" }).click();
  const skip = page.getByRole("button", { name: "Skip" });
  await expect(skip).toBeFocused();
  await skip.press("Enter");
  await expect(roomTitle(page)).toBeFocused();
  const ghost = hero(page).getByRole("button", {
    name: "Open in the demo: Swollen ankles, then an added water pill",
  });
  await page.keyboard.press("Tab");
  await expect(ghost).toBeFocused();
  await expect(ghost).toBeInViewport();
  await ghost.press("Enter");
  await expect(page).toHaveURL(/\/en\/results\/finding#1$/);
  await expect(page.getByTestId("demo-label")).toBeVisible();
  await expect(page.getByTestId("finding")).toContainText(
    "Order fits the pattern",
  );
});

test("Step inside plays the door video once at normal speed, then scene 3 and Replay", async ({
  page,
}) => {
  await page.goto("/en", { waitUntil: "networkidle" });
  await hero(page).getByRole("button", { name: "Step inside" }).click();
  await expect(hero(page)).toHaveAttribute("data-scene", "door");
  const v = page.locator("[data-video]");
  await expect
    .poll(() => v.evaluate((e: HTMLVideoElement) => e.currentTime), {
      timeout: 8000,
    })
    .toBeGreaterThan(0.5);
  expect(
    await v.evaluate((e: HTMLVideoElement) => [
      e.paused,
      e.playbackRate,
      e.loop,
    ]),
  ).toEqual([false, 1, false]);
  await expect(roomTitle(page)).toBeFocused({ timeout: 20_000 });
  await expect(hero(page)).toHaveAttribute("data-scene", "room");
  expect(await v.evaluate((e: HTMLVideoElement) => e.ended)).toBe(true);
  await hero(page).getByRole("button", { name: "Replay the way in" }).click();
  await expect(hero(page)).toHaveAttribute("data-scene", "door");
});

for (const [name, setup] of [
  [
    "reduced motion",
    async (page: Page) => page.emulateMedia({ reducedMotion: "reduce" }),
  ],
  [
    "Save-Data",
    async (page: Page) =>
      page.addInitScript(() => {
        Object.defineProperty(navigator, "connection", {
          value: { saveData: true, effectiveType: "4g" },
        });
      }),
  ],
] as const)
  test(`${name}: step inside goes straight to scene 3, still ghosts, no video request`, async ({
    page,
  }) => {
    await setup(page);
    const requests = recordRequests(page);
    await page.goto("/en", { waitUntil: "networkidle" });
    if (name === "Save-Data")
      await expect(hero(page)).toHaveAttribute("data-still", "save-data");
    await hero(page).getByRole("button", { name: "Step inside" }).click();
    await expect(roomTitle(page)).toBeFocused();
    await expect(page.locator(".np-cabinet img")).toBeVisible();
    const animation = await page
      .locator(".np-cabinet .np-ghost")
      .first()
      .evaluate((e) => getComputedStyle(e).animationName);
    expect(animation).toBe("none");
    await page.waitForTimeout(800);
    expect(requests.filter((r) => video(r.url()))).toHaveLength(0);
    // Replay goes back to the street, to the button.
    await hero(page).getByRole("button", { name: "Replay the way in" }).click();
    await expect(
      hero(page).getByRole("button", { name: "Step inside" }),
    ).toBeFocused();
  });

test("Glass Janus: its own hero only, no ghosts, no Night Pharmacy image", async ({
  page,
}) => {
  await useTheme(page, "glass");
  const requests = recordRequests(page);
  await page.goto("/en");
  await expect(
    page.locator("#content").getByTestId("glass-hero"),
  ).toBeVisible();
  await expect(page.locator("#content").getByTestId("night-hero")).toHaveCount(
    0,
  );
  await page.waitForLoadState("networkidle");
  expect(requests.filter((r) => /night-|door-/.test(r.url()))).toHaveLength(0);
  expect(requests.some((r) => /glass-hero-\d+\.avif/.test(r.url()))).toBe(true);
});

test("LCP of the home (recorded)", async ({ page }, info) => {
  const cdp = await page.context().newCDPSession(page);
  // "Desktop throttled": 4× CPU slow-down and a fast 4G-like network.
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 40,
    downloadThroughput: (9 * 1024 * 1024) / 8,
    uploadThroughput: (1.5 * 1024 * 1024) / 8,
  });
  await page.goto("/en", { waitUntil: "load" });
  const metrics = await page.evaluate(
    () =>
      new Promise<{ lcp: number; element: string; cls: number }>((resolve) => {
        let lcp = 0,
          element = "",
          cls = 0;
        new PerformanceObserver((l) => {
          for (const e of l.getEntries() as (PerformanceEntry & {
            element?: Element;
          })[]) {
            lcp = e.startTime;
            element = e.element?.tagName ?? "";
          }
        }).observe({ type: "largest-contentful-paint", buffered: true });
        new PerformanceObserver((l) => {
          for (const e of l.getEntries() as (PerformanceEntry & {
            value: number;
            hadRecentInput: boolean;
          })[])
            if (!e.hadRecentInput) cls += e.value;
        }).observe({ type: "layout-shift", buffered: true });
        setTimeout(() => resolve({ lcp, element, cls }), 3000);
      }),
  );
  info.annotations.push({
    type: "metrics",
    description: `LCP ${Math.round(metrics.lcp)} ms (${metrics.element}), CLS ${metrics.cls.toFixed(3)}`,
  });
  console.log(
    `[${info.project.name}] LCP ${Math.round(metrics.lcp)} ms (${metrics.element}), CLS ${metrics.cls.toFixed(3)}`,
  );
  expect(metrics.cls).toBeLessThan(0.1);
  expect(metrics.lcp).toBeLessThan(4000);
});

test("the emergency bar is on the first screen, under the header, also in demo mode", async ({
  page,
}) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  await page.goto("/en", { waitUntil: "networkidle" });
  const bar = page.locator("#content").getByTestId("emergency-notice");
  await expect(bar).toBeInViewport();
  const header = await page.locator("header").first().boundingBox();
  const box = await bar.boundingBox();
  expect(box!.y).toBeGreaterThanOrEqual(header!.y + header!.height - 1);
  // It opens to the full text.
  await bar.locator("summary").click();
  await expect(bar).toContainText("Chest pain");
});

// Home scenes (experience Req 27.6–27.8, DP46): the Night Pharmacy findings are real buttons
// into the demo; reduced motion shows the stills and never requests the video; each theme loads
// only its own hero image; the LCP is measured and recorded.
import { expect, test } from "@playwright/test";

import { recordRequests, useTheme } from "./helpers";

const video = (url: string) => /\/home\/door-\d+\.(mp4|webm)$/.test(url);

test("Night Pharmacy: the ghosts open the Istanbul demo findings", async ({
  page,
}) => {
  await page.goto("/en", { waitUntil: "networkidle" });
  const ghost = page.locator("#content").getByRole("button", {
    name: "Open in the demo: Swollen ankles, then an added water pill",
  });
  await expect(ghost).toBeAttached();
  // Keyboard order: hero actions first, then step inside, then the findings.
  const order = await page.evaluate(() =>
    [
      ...document.querySelectorAll<HTMLElement>(
        "#content .np a, #content .np button",
      ),
    ].map((e) => e.textContent?.trim() ?? ""),
  );
  expect(order.slice(0, 3)).toEqual([
    "Try the demo",
    "How it works",
    "Step inside↓",
  ]);
  await ghost.focus();
  await expect(ghost).toBeInViewport();
  await ghost.press("Enter");
  await expect(page).toHaveURL(/\/en\/results\/finding#1$/);
  await expect(page.getByTestId("demo-label")).toBeVisible();
  await expect(page.getByTestId("finding")).toContainText(
    "Order fits the pattern",
  );
});

test("reduced motion: the three stills, still ghosts, no video request", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const requests = recordRequests(page);
  await page.goto("/en");
  await page.evaluate(() => scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(800);
  await expect(page.locator(".np-still-img img")).toBeVisible();
  await expect(page.locator(".np-cabinet img")).toBeVisible();
  const animation = await page
    .locator(".np-ghost")
    .first()
    .evaluate((e) => getComputedStyle(e).animationName);
  expect(animation).toBe("none");
  expect(requests.filter((r) => video(r.url()))).toHaveLength(0);
});

test("Save-Data: stills, no video request", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "connection", {
      value: { saveData: true, effectiveType: "4g" },
    });
  });
  const requests = recordRequests(page);
  await page.goto("/en", { waitUntil: "networkidle" });
  await expect(
    page.locator("#content").getByTestId("night-hero"),
  ).toHaveAttribute("data-still", "save-data");
  await page.waitForTimeout(500);
  expect(requests.filter((r) => video(r.url()))).toHaveLength(0);
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

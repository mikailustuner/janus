// Cascade map (cascade-map tasks 6–7): map and list, filters, keyboard flow, panel, axe, both
// themes, five locales (E2E_LOCALES), no network in the demo, reduced motion, and the performance
// measurement of design §7 (375 px, CPU 4×).
import { readFileSync } from "node:fs";
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
  recordRequests,
  stubApi,
  THEMES,
  useTheme,
} from "./helpers";

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
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

async function demo(page: Page) {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
}

async function open(page: Page, locale = "en") {
  await page.goto(`/${locale}/cascades`);
  await expect(page.getByTestId("cascade-map")).toBeVisible();
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, {
    timeout: 15_000,
  });
}

async function common(
  page: Page,
  locale: (typeof LOCALES)[number],
  theme: string,
) {
  await expect(page.getByTestId("disclaimer")).toHaveText(
    messages[locale].Disclaimer.text,
  );
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  const text = await page.locator("body").innerText();
  expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
  if (theme === "glass")
    expect(findForbiddenPhrases(text, themeWords[locale])).toEqual([]);
}

for (const theme of THEMES)
  for (const locale of locales)
    test(`map, list and panel, ${locale}, ${theme}`, async ({ page }) => {
      await useTheme(page, theme);
      await demo(page);
      const requests = recordRequests(page);
      await open(page, locale);
      const m = messages[locale].CascadeMap;
      await expect(page.getByTestId("cm-framing")).toHaveText(m.framing);
      // Every PIPC rule exactly once on the map; the Istanbul findings highlighted.
      await expect(page.locator('[data-testid^="edge-"]')).toHaveCount(65);
      await expect(page.locator("[data-node]")).toHaveCount(65);
      await expect(page.locator(".cm-e-matched")).toHaveCount(4);
      for (const row of [5, 6, 9, 12])
        await expect(page.getByTestId(`edge-${row}`)).toHaveClass(
          /cm-e-matched/,
        );
      await expect(page.getByTestId("edge-27")).toHaveClass(/cm-e-cannot/);
      await common(page, locale, theme);

      // List view: every rule exactly once, in row order.
      await page
        .getByRole("button", { name: m.views.list, exact: true })
        .click();
      await expect(page.locator('[data-testid^="row-"]')).toHaveCount(65);
      await expect(
        page.locator('[data-testid^="row-"]').first(),
      ).toHaveAttribute("data-testid", "row-1");
      await common(page, locale, theme);

      // Panel of a pattern that cannot be checked.
      await page.getByTestId("row-27").getByRole("button").click();
      const panel = page.getByTestId("cm-panel");
      await expect(panel).toBeVisible();
      await expect(panel.getByTestId("cm-cannot")).toBeVisible();
      await expect(panel).toContainText("rule:pipc:27");
      await expect(panel).toContainText(
        messages[locale].Findings.source.replace("{row}", "27"),
      );
      await expectNoAxeViolations(page);
      await page.keyboard.press("Escape");
      await expect(panel).toHaveCount(0);
      await expect(
        page.getByTestId("row-27").getByRole("button"),
      ).toBeFocused();

      // C4: nothing reaches the network in the demo.
      expect(
        requests.filter(
          (r) =>
            new URL(r.url()).origin !== new URL(page.url()).origin &&
            !r.url().startsWith("data:"),
        ),
      ).toEqual([]);
      expect(
        requests.filter((r) => new URL(r.url()).pathname.startsWith("/api/")),
      ).toEqual([]);
    });

test("panel of a matched pattern links to the finding", async ({ page }) => {
  await demo(page);
  await open(page);
  await page.getByRole("button", { name: "List", exact: true }).click();
  await page.getByTestId("row-5").getByRole("button").click();
  const panel = page.getByTestId("cm-panel");
  await expect(panel.getByRole("heading", { level: 2 })).toBeFocused();
  await expect(panel).toContainText("Row 5");
  await expect(panel).toContainText(
    "Source: PIPC list (Rochon et al., Eur Geriatr Med 2025), row 5.",
  );
  await expect(panel).toContainText("paper:thinkcascades:drugs_aging_2022");
  const yours = panel.getByTestId("cm-yours");
  await expect(yours).toContainText("(demo)");
  await expect(
    yours.getByRole("link", { name: "Evidence and reports" }),
  ).toHaveAttribute("href", /\/results\/finding#\d+$/);
  await panel.getByRole("button", { name: "Close" }).click();
  await expect(panel).toHaveCount(0);
});

test("keyboard: one star in the tab order, arrows move, Enter opens, Escape returns", async ({
  page,
}) => {
  await demo(page);
  await open(page);
  await expect(page.locator('[data-node][tabindex="0"]')).toHaveCount(1);
  await page.locator('[data-node][tabindex="0"]').focus();
  const first = await page.evaluate(() =>
    document.activeElement?.getAttribute("data-node"),
  );
  const seen = new Set([first]);
  for (const key of [
    "ArrowRight",
    "ArrowDown",
    "ArrowLeft",
    "ArrowUp",
    "ArrowDown",
    "ArrowRight",
  ]) {
    await page.keyboard.press(key);
    seen.add(
      await page.evaluate(() =>
        document.activeElement?.getAttribute("data-node"),
      ),
    );
  }
  expect(seen.size).toBeGreaterThan(2);
  await expect(page.locator('[data-node][tabindex="0"]')).toHaveCount(1);
  await page.keyboard.press("Home");
  const home = await page.evaluate(() =>
    document.activeElement?.getAttribute("data-node"),
  );
  expect(home).toBeTruthy();
  await page.keyboard.press("Enter");
  const panel = page.getByTestId("cm-panel");
  await expect(panel.getByRole("heading", { level: 2 })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);
  await expect(page.locator(`[data-node="${home}"]`)).toBeFocused();
  // The accessible name says what the star is.
  await expect(page.locator('[data-node="statin"]')).toHaveAttribute(
    "aria-label",
    /HMG Co-A reductase inhibitor: first medicine in 4 patterns, second medicine in 0 patterns\. Part of a finding for your list\./,
  );
});

test("filters only remove, announce the count and have an empty state", async ({
  page,
}) => {
  await demo(page);
  await open(page);
  const before = await page
    .locator('[data-node="statin"]')
    .getAttribute("transform");
  await page.getByLabel("Medicine class").selectOption("statin");
  await expect(page.getByTestId("cm-count")).toHaveText(
    "4 of 65 patterns shown",
  );
  await expect(page.locator('[data-testid^="edge-"]')).toHaveCount(4);
  expect(
    await page.locator('[data-node="statin"]').getAttribute("transform"),
  ).toBe(before);
  await page.getByLabel("Side effect").selectOption("myalgia_myositis");
  await expect(page.getByTestId("cm-count")).toHaveText(
    "3 of 65 patterns shown",
  );
  await page.getByLabel("Search").fill("zzzz");
  await expect(page.getByText("No pattern fits these filters.")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).first().click();
  await expect(page.getByTestId("cm-count")).toHaveText(
    "65 of 65 patterns shown",
  );
});

test("without a list: no highlights, an invitation, no request", async ({
  page,
}) => {
  const seen = await stubApi(page);
  await open(page);
  await expect(page.getByTestId("cm-matches")).toContainText(
    "Add medicines to see which patterns match your list.",
  );
  await expect(page.locator(".cm-e-matched")).toHaveCount(0);
  await expect(page.locator(".cm-e-cannot")).toHaveCount(2);
  // The plain-route checks of routes.spec.ts (the screen is listed there under DEMO only).
  await common(page, "en", "two-faces");
  expect(seen).toEqual([]);
});

test("reduced motion: the zoom buttons jump without easing", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await demo(page);
  await open(page);
  const layer = page.locator("[data-testid=cascade-map] svg[role=group] > g");
  const t0 = await layer.getAttribute("transform");
  await page.getByRole("button", { name: "Zoom in" }).click();
  await page.evaluate(
    () =>
      new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
  );
  const t1 = await layer.getAttribute("transform");
  await page.waitForTimeout(300);
  expect(t1).not.toBe(t0);
  expect(await layer.getAttribute("transform")).toBe(t1);
});

test("performance: no long task over 50 ms while panning, zooming and filtering (375 px, CPU 4x)", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "phone", "measured at 375 px");
  await page.addInitScript(() => {
    const w = window as unknown as {
      __long: { start: number; duration: number }[];
    };
    w.__long = [];
    new PerformanceObserver((list) => {
      for (const e of list.getEntries())
        w.__long.push({ start: e.startTime, duration: e.duration });
    }).observe({ type: "longtask", buffered: true });
  });
  await demo(page);
  await open(page);
  await page.getByTestId("cascade-map").scrollIntoViewIfNeeded();
  // Button centres are read before throttling: raw mouse clicks keep Playwright's own
  // actionability checks (which run in the page) out of the measurement.
  const centre = async (name: string) => {
    const b = (await page.getByRole("button", { name }).boundingBox())!;
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
  };
  const zoomIn = await centre("Zoom in");
  const zoomOut = await centre("Zoom out");
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.waitForTimeout(500);
  const start = await page.evaluate(() => {
    const w = window as unknown as { __frames: number[]; __stop: boolean };
    w.__frames = [];
    w.__stop = false;
    let last = performance.now();
    const tick = (now: number) => {
      w.__frames.push(now - last);
      last = now;
      if (!w.__stop) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    return performance.now();
  });

  const mark = (name: string) =>
    page.evaluate((n) => {
      const w = window as unknown as { __phases?: { n: string; t: number }[] };
      (w.__phases ??= []).push({ n, t: performance.now() });
    }, name);
  const box = (await page.getByTestId("cascade-map").boundingBox())!;
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  // Pan: a 40-step drag there and back.
  await mark("pan");
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  for (let i = 1; i <= 40; i++) await page.mouse.move(cx + i * 3, cy + i * 2);
  for (let i = 40; i >= 0; i--) await page.mouse.move(cx + i * 3, cy + i * 2);
  await page.mouse.up();
  // Zoom: buttons and Ctrl + wheel.
  await mark("zoom");
  for (const at of [zoomIn, zoomIn, zoomIn, zoomOut, zoomOut, zoomOut]) {
    await page.mouse.click(at.x, at.y);
    await page.waitForTimeout(250);
  }
  await mark("wheel");
  await page.keyboard.down("Control");
  for (let i = 0; i < 6; i++) await page.mouse.wheel(0, i < 3 ? -120 : 120);
  await page.keyboard.up("Control");
  // Filters.
  await mark("filter");
  await page.getByLabel("Medicine class").selectOption("antipsychotic");
  await page.getByLabel("Medicine class").selectOption("");
  await page.getByLabel("Search").fill("nausea");
  await page.getByLabel("Search").fill("");
  await page.waitForTimeout(400);

  const r = await page.evaluate((t0) => {
    const w = window as unknown as {
      __frames: number[];
      __stop: boolean;
      __long: { start: number; duration: number }[];
      __phases: { n: string; t: number }[];
    };
    w.__stop = true;
    const phaseOf = (t: number) =>
      [...w.__phases].reverse().find((p) => p.t <= t)?.n ?? "before";
    const frames = w.__frames.slice(1).sort((a, b) => a - b);
    const q = (p: number) =>
      frames[Math.min(frames.length - 1, Math.floor(p * frames.length))] ?? 0;
    const long = w.__long.filter((l) => l.start >= t0);
    return {
      frames: frames.length,
      median: q(0.5),
      p95: q(0.95),
      long: long.map((l) => Math.round(l.duration)),
      phases: long.map((l) => `${phaseOf(l.start)}:${Math.round(l.duration)}`),
    };
  }, start);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  const load = (await import("node:os")).loadavg()[0]!.toFixed(1);
  const summary = `host load ${load}; frames=${r.frames} median=${r.median.toFixed(1)}ms p95=${r.p95.toFixed(1)}ms longTasks=${JSON.stringify(r.phases)}`;
  info.annotations.push({ type: "performance", description: summary });
  console.log(`cascade-map performance: ${summary}`);
  // CPU throttling multiplies whatever else the host runs: the budget is asserted only on a host
  // that is not saturated (other test workers, builds); the numbers are recorded either way.
  const os = await import("node:os");
  const busy = os.loadavg()[0]! / os.cpus().length > 0.75;
  if (busy)
    info.annotations.push({
      type: "not asserted",
      description: "host saturated",
    });
  else expect(r.long.filter((d) => d > 50)).toEqual([]);
});

test("a matched pattern with an urgent-care event shows the emergency notice first (Cologne, row 51)", async ({
  page,
}) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "cologne"),
  );
  await open(page);
  await page.getByRole("button", { name: "List", exact: true }).click();
  await page.getByTestId("row-51").getByRole("button").click();
  const panel = page.getByTestId("cm-panel");
  await expect(panel.locator("[data-testid]").first()).toHaveAttribute(
    "data-testid",
    "emergency-notice",
  );
  await expect(panel.getByTestId("safety-line")).toHaveAttribute(
    "data-code",
    "urgent_care_gi",
  );
  // A pattern without a finding for the list has neither.
  await page.keyboard.press("Escape");
  await page.getByTestId("row-52").getByRole("button").click();
  await expect(panel.getByTestId("emergency-notice")).toHaveCount(0);
  await expect(panel.getByTestId("cm-yours")).toContainText(
    "None of the findings for your list uses this pattern.",
  );
});

// janus-report (design §6, P9; Req 1, 2, 5, 6): the Summary from the Istanbul demo, tiles that
// lead into the detail, the share flow with its confirmation and the downloaded PNG's size, no
// request at all, axe, touch targets and no horizontal scroll at 375 / 1280, both themes, the five
// locales (E2E_LOCALES as in routes.spec.ts).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page, type Request } from "@playwright/test";

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
async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, {
    timeout: 15_000,
  });
}
/** C4: nothing reaches the API and nothing leaves the origin. */
function expectNoRequest(page: Page, requests: Request[]) {
  expect(
    requests
      .filter((r) => new URL(r.url()).pathname.startsWith("/api/"))
      .map((r) => r.url()),
  ).toEqual([]);
  const origin = new URL(page.url()).origin;
  expect(
    requests
      .map((r) => r.url())
      .filter(
        (u) =>
          !u.startsWith("data:") &&
          !u.startsWith("blob:") &&
          new URL(u).origin !== origin,
      ),
  ).toEqual([]);
}
/** Width and height from a PNG's IHDR chunk. */
function pngSize(buf: Buffer) {
  expect(buf.subarray(1, 4).toString("latin1")).toBe("PNG");
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}
async function noWebShare(page: Page) {
  await page.addInitScript(() => {
    Object.defineProperty(Navigator.prototype, "share", { value: undefined });
    Object.defineProperty(Navigator.prototype, "canShare", {
      value: undefined,
    });
  });
}

for (const theme of THEMES)
  for (const locale of locales)
    test(`summary from the demo, ${locale}, ${theme}`, async ({ page }) => {
      const m = messages[locale];
      await useTheme(page, theme);
      await demo(page);
      const requests = recordRequests(page);
      await page.goto(`/${locale}/results/summary`);
      await settled(page);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(
        m.Report.title,
      );
      await expect(page.getByTestId("demo-label")).toBeVisible();
      await expect(page.getByTestId("disclaimer")).toHaveText(
        m.Disclaimer.text,
      );
      // Istanbul: 9 medicines, 4 findings (3 order fits, 1 not confirmed), 2 warned items.
      await expect(page.getByTestId("summary-finding")).toHaveCount(4);
      await expect(
        page.getByTestId("group-fits").getByTestId("summary-finding"),
      ).toHaveCount(3);
      await expect(
        page.getByTestId("group-notConfirmed").getByTestId("summary-finding"),
      ).toHaveCount(1);
      await expect(
        page.getByTestId("tile-abrupt").getByTestId("abrupt-stop"),
      ).toHaveCount(2);
      await expect(page.getByTestId("summary-integrity")).toContainText(
        m.Evidence.line.noRetracted,
      );
      await expect(page.getByTestId("source-row")).toHaveCount(1);
      // The emergency notice is not shown: no Istanbul event has a safety line.
      await expect(page.getByTestId("emergency-notice")).toHaveCount(0);
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      const text = await page.locator("body").innerText();
      expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
      if (theme === "glass")
        expect(findForbiddenPhrases(text, themeWords[locale])).toEqual([]);

      // The confirmation dialog passes the same checks.
      await noWebShare(page);
      await page.getByTestId("share-prepare").click();
      await expect(page.getByTestId("share-dialog")).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByTestId("share-preview")).toBeVisible();
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("share-dialog")).toBeHidden();
      expectNoRequest(page, requests);
    });

test("the results link to the Summary and every tile leads into the detail", async ({
  page,
}) => {
  await demo(page);
  const requests = recordRequests(page);
  await page.goto("/en/results");
  await settled(page);
  await page.getByTestId("summary-link").getByRole("link").click();
  await expect(page).toHaveURL(/\/en\/results\/summary$/);
  await settled(page);
  const tiles: [string, RegExp][] = [
    ["tile-medicines", /\/en\/medicines$/],
    ["tile-rules", /\/en\/results#scope$/],
    ["tile-abrupt", /\/en\/medicines$/],
    ["tile-regions", /\/en\/passport$/],
    ["tile-sources", /\/en\/passport$/],
    ["tile-patterns", /\/en\/results$/],
  ];
  for (const [tile, url] of tiles) {
    await page.getByTestId(`${tile}-link`).click();
    await expect(page).toHaveURL(url);
    await page.goto("/en/results/summary");
    await settled(page);
  }
  // A finding row opens its detail; the evidence row opens the first finding's detail.
  await page.getByTestId("group-notConfirmed").getByRole("link").click();
  await expect(page).toHaveURL(/\/en\/results\/finding#3$/);
  await expect(page.getByTestId("finding")).toBeVisible();
  expectNoRequest(page, requests);
});

test("share flow: counts only by default, opt-ins, confirmation, a 1080 x 1350 PNG download, no request", async ({
  page,
}) => {
  await demo(page);
  await noWebShare(page);
  const requests = recordRequests(page);
  await page.goto("/en/results/summary");
  await settled(page);
  const m = messages.en;
  const eventNames = await page.getByTestId("summary-finding").allInnerTexts();
  expect(eventNames.length).toBe(4);

  // Default: counts only.
  await expect(page.getByTestId("share-events")).not.toBeChecked();
  await expect(page.getByTestId("share-ingredients")).not.toBeChecked();
  const prepare = page.getByTestId("share-prepare");
  await prepare.click();
  const dialog = page.getByTestId("share-dialog");
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await expect(dialog).toContainText(m.Report.share.confirmText);
  const preview = page.getByTestId("share-preview");
  const alt = (await preview.getAttribute("alt")) ?? "";
  expect(alt).toContain("9 medicines checked · 4 patterns to discuss");
  expect(alt).toContain("checked against 63 of 65 patterns");
  expect(alt).toContain(m.Disclaimer.text);
  expect(alt).toContain(m.Demo.label);
  expect(alt).toContain("Do not stop this medicine suddenly.");
  for (const e of eventNames) expect(alt).not.toContain(e);
  expect(alt).not.toContain("(demo)"); // no box name
  expect(alt.toLowerCase()).not.toContain("sertraline");
  const size = await preview.evaluate((img: HTMLImageElement) => ({
    w: img.naturalWidth,
    h: img.naturalHeight,
  }));
  expect(size).toEqual({ w: 1080, h: 1350 });
  // Focus is inside the dialog; the Share button is absent without Web Share.
  await expect(page.getByTestId("share-share")).toHaveCount(0);
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("share-save").click(),
  ]);
  expect(download.suggestedFilename()).toBe("janus-summary-2026-11.png");
  const file = await download.path();
  expect(pngSize(readFileSync(file))).toEqual({ width: 1080, height: 1350 });
  await expect(dialog).toBeHidden();
  await expect(page.getByText(m.Report.share.saved)).toBeVisible();

  // Opt in to both: the event names and the ingredient names are on the image, box names never.
  await page.getByTestId("share-events").check();
  await page.getByTestId("share-ingredients").check();
  await prepare.click();
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  const alt2 = (await preview.getAttribute("alt")) ?? "";
  for (const e of eventNames) expect(alt2).toContain(e);
  expect(alt2.toLowerCase()).toContain("sertraline");
  expect(alt2).not.toContain("(demo)");
  await page.getByTestId("share-cancel").click();
  await expect(dialog).toBeHidden();
  await expect(prepare).toBeFocused();
  expectNoRequest(page, requests);
});

test("share flow with Web Share: the file goes to the share sheet; a cancelled share keeps the dialog", async ({
  page,
}) => {
  await demo(page);
  await page.addInitScript(() => {
    const w = window as unknown as { __shared: number[]; __abort: boolean };
    w.__shared = [];
    w.__abort = true;
    Object.defineProperty(Navigator.prototype, "canShare", {
      value: (d: { files?: File[] }) => !!d.files?.length,
    });
    Object.defineProperty(Navigator.prototype, "share", {
      value: async (d: { files: File[] }) => {
        if (w.__abort) {
          w.__abort = false;
          throw new DOMException("cancelled", "AbortError");
        }
        w.__shared.push(d.files[0]!.size);
      },
    });
  });
  const requests = recordRequests(page);
  await page.goto("/en/results/summary");
  await settled(page);
  await page.getByTestId("share-prepare").click();
  const dialog = page.getByTestId("share-dialog");
  await page.getByTestId("share-share").click();
  await expect(dialog).toBeVisible(); // cancelled: still open, no error
  await page.getByTestId("share-share").click();
  await expect(dialog).toBeHidden();
  const shared = await page.evaluate(
    () => (window as unknown as { __shared: number[] }).__shared,
  );
  expect(shared.length).toBe(1);
  expect(shared[0]).toBeGreaterThan(10_000);
  expectNoRequest(page, requests);
});

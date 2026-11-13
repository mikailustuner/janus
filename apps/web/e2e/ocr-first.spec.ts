// ocr-first tasks 7–8: the three ways in, the path from "code not found" to a confirmed ingredient
// by a label photo, and every state of the label panel (camera refused, no camera, reading
// failed, nothing recognised, no ingredient recognised), with axe, no horizontal scroll and
// 44 px targets, in five languages and both themes. Label images are drawn in the browser; the
// API is stubbed; nothing of a label is sent before a choice and then only the chosen name.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Browser, type Page } from "@playwright/test";

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

const read = (p: string) =>
  JSON.parse(readFileSync(join(import.meta.dirname, p), "utf8"));
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../messages/${l}.json`)]),
);
const m = messages.en;
const cologne = read("../src/demo/fixtures/cologne.json");
const istanbul = read("../src/demo/fixtures/istanbul.json");
// A name search answer: a product first (as the API ranks it), then the ingredient ambroxol.
const ambroxol = cologne.items[1].resolution;
const searchAnswer = {
  ...ambroxol,
  candidates: [
    istanbul.items[1].resolution.candidates[0],
    ...ambroxol.candidates,
  ],
};
const notFound = { ...ambroxol, candidates: [], regions_searched: ["EU"] };
const noOpenDatabase = {
  ...notFound,
  notices: [
    {
      code: "no_open_product_database",
      region: "EU",
      country: "DE",
      source_id: null,
      date: null,
    },
  ],
};

const shots = join(import.meta.dirname, "../test-results/ocr-first");
mkdirSync(shots, { recursive: true });
const shot = (page: Page, name: string) =>
  page.screenshot({
    path: join(
      shots,
      `${name}-${page.viewportSize()!.width === 375 ? "375" : "1280"}.png`,
    ),
    fullPage: true,
  });

/** A label drawn as rendered text and photographed in the browser. Not a real box. */
async function label(browser: Browser, lines: string[]): Promise<Buffer> {
  const painter = await browser.newPage({
    viewport: { width: 900, height: 120 + 60 * lines.length },
  });
  await painter.setContent(
    `<body style="margin:0;background:#fff;font:34px/1.6 Arial;padding:24px">${lines
      .map((l) => `<div>${l}</div>`)
      .join("")}</body>`,
  );
  const png = await painter.screenshot();
  await painter.close();
  return png;
}

const GERMAN_BOX = [
  "Mucovor 30 mg",
  "Ambroxolhydrochlorid",
  "Hydrochlorothiazid 12,5 mg",
  "20 Tabletten · Zum Einnehmen",
];

async function pick(page: Page, png: Buffer, locale = "en") {
  await page
    .getByLabel(messages[locale].Scan.ocr.pick)
    .setInputFiles({ name: "label.png", mimeType: "image/png", buffer: png });
}

for (const locale of LOCALES)
  for (const theme of THEMES)
    test(`three ways in and the any-country line: ${locale}, ${theme}`, async ({
      page,
    }) => {
      const s = messages[locale].Scan;
      await useTheme(page, theme);
      await stubApi(page);
      await page.goto(`/${locale}/scan`);
      const tabs = page.getByRole("tab");
      await expect(tabs).toHaveCount(3);
      await expect(tabs).toHaveText([s.tabs.code, s.tabs.label, s.tabs.type]);
      await expect(
        page.locator("#content").getByTestId("any-country"),
      ).toHaveText(s.anyCountry);
      // Equal controls: one row, the same size.
      const boxes = await tabs.evaluateAll((els) =>
        els.map((e) => e.getBoundingClientRect()),
      );
      for (const b of boxes) {
        expect(Math.abs(b.width - boxes[0]!.width)).toBeLessThan(1);
        expect(Math.abs(b.height - boxes[0]!.height)).toBeLessThan(1);
        expect(b.y).toBe(boxes[0]!.y);
      }
      await expect(page.getByText(s.codeLead)).toBeVisible();
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      await shot(page, `scan-code-${locale}-${theme}`);

      await tabs.nth(1).click();
      await expect(page.getByText(s.labelLead)).toBeVisible();
      await expect(page.getByText(s.ocr.privacy)).toBeVisible();
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      await shot(page, `scan-label-${locale}-${theme}`);

      await tabs.nth(2).click();
      await expect(page.getByText(s.typeLead)).toBeVisible();
      await expectNoAxeViolations(page);
      await expectTouchTargets(page);
    });

test("code not found → label photo → candidates → confirm → the second ingredient is still there", async ({
  page,
  browser,
}) => {
  test.setTimeout(180_000);
  const requests = recordRequests(page);
  const seen = await stubApi(page, {
    "/resolve/scan": { body: notFound },
    "/resolve/search": { body: searchAnswer },
  });
  await page.goto("/en/scan");
  await page.getByRole("tab", { name: m.Scan.tabs.type }).click();
  await page.getByLabel(m.Scan.typeLabel).fill("4150000000015");
  await page.getByRole("button", { name: m.Scan.submit, exact: true }).click();

  // Not found is said with what was searched, and it is not a dead end.
  await expect(page.getByTestId("not-found")).toContainText(
    "No medicine was found in",
  );
  const ways = page.getByTestId("other-ways");
  await expect(ways).toContainText(m.Confirm.tryOther);
  await expectNoAxeViolations(page);
  await expectTouchTargets(page);
  await shot(page, "confirm-not-found-en");
  await ways.getByRole("link", { name: m.Scan.wayLabel }).click();
  await expect(
    page.getByRole("tab", { name: m.Scan.tabs.label }),
  ).toHaveAttribute("aria-selected", "true");

  const before = seen.length;
  await pick(page, await label(browser, GERMAN_BOX));
  // Loading feedback while the label is read on the device.
  await expect(page.getByTestId("label-reading")).toBeVisible();
  await expect(page.getByTestId("label-reading")).toHaveAttribute(
    "aria-busy",
    "true",
  );
  const candidates = page.getByTestId("label-candidate");
  await expect(candidates).toHaveCount(2, { timeout: 90_000 });
  // Strongest first (ingredient-match.ts): the exact name, then the name joined to its salt.
  await expect(candidates.nth(0)).toContainText("hydrochlorothiazide");
  await expect(candidates.nth(1)).toContainText("ambroxol");
  await expect(candidates.nth(1)).toContainText(
    "On the label: Ambroxolhydrochlorid",
  );
  await expect(page.getByText(m.Scan.ocr.several)).toBeVisible();
  // Nothing is chosen and nothing was sent.
  await expect(
    page.locator("[aria-pressed=true], [aria-checked=true]"),
  ).toHaveCount(0);
  expect(seen.length).toBe(before);
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  await shot(page, "label-candidates-en");

  await candidates.filter({ hasText: "ambroxol" }).click();
  await expect(
    page.getByRole("heading", { name: m.Confirm.title }),
  ).toBeVisible();
  const search = seen.filter((r) => r.url().endsWith("/api/resolve/search"));
  expect(search).toHaveLength(1);
  // Only the held English name of the chosen ingredient leaves the device.
  expect(search[0]!.postDataJSON()).toEqual({ query: "ambroxol", limit: 20 });
  // The chosen ingredient is listed first, before the product the API ranked first; nothing is
  // preselected.
  const cards = page.getByTestId("candidate");
  await expect(cards).toHaveCount(2);
  await expect(cards.nth(0).getByRole("heading")).toHaveText("ambroxol");
  await page.getByRole("button", { name: "Add to my medicines" }).click();
  await expect(
    page.getByText("Please choose one medicine first."),
  ).toBeVisible();
  await cards.nth(0).getByRole("button", { name: "This one" }).click();
  await page.getByRole("button", { name: "Add to my medicines" }).click();
  await expect(page).toHaveURL(/\/en\/medicines$/);
  // The item added is the card the user tapped (the second candidate of the answer), not the
  // card at that place in the answer.
  const stored = await page.evaluate(
    () => JSON.parse(localStorage.getItem("janus.v1.list")!).items,
  );
  expect(stored).toHaveLength(1);
  expect(stored[0].candidate.ingredient_key.qid).toBe("Q221637");

  // Back on the scan screen the label result is still there for the second ingredient.
  await page.getByRole("link", { name: m.Medicines.add }).first().click();
  await expect(
    page.getByRole("tab", { name: m.Scan.tabs.label }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(candidates).toHaveCount(2);
  await expect(candidates.filter({ hasText: "ambroxol" })).toContainText(
    m.Scan.ocr.inList,
  );
  await expect(
    candidates.filter({ hasText: "hydrochlorothiazide" }),
  ).not.toContainText(m.Scan.ocr.inList);
  await page.getByRole("button", { name: m.Scan.ocr.remove }).click();
  await expect(candidates).toHaveCount(0);

  const origin = new URL(page.url()).origin;
  for (const r of requests) {
    expect(r.url().startsWith(origin) || /^(data|blob):/.test(r.url())).toBe(
      true,
    );
    const body = r.postData() ?? "";
    expect(body.length).toBeLessThanOrEqual(8192);
    expect(body).not.toMatch(/Mucovor|hydrochlorid|Tabletten/i);
    expect(r.headers()["content-type"] ?? "").not.toMatch(/^image\//);
  }
});

test("a country without a product database leads to the label photo and the name", async ({
  page,
}) => {
  await stubApi(page, { "/resolve/scan": { body: noOpenDatabase } });
  await page.goto("/en/scan");
  await page.getByRole("tab", { name: m.Scan.tabs.type }).click();
  await page.getByLabel(m.Scan.typeLabel).fill("4150000000015");
  await page.getByRole("button", { name: m.Scan.submit, exact: true }).click();
  await expect(page.getByTestId("no-open-database")).toHaveText(
    m.Confirm.noOpenDatabase,
  );
  await expect(page.getByTestId("not-found")).toHaveCount(0);
  const ways = page.getByTestId("other-ways");
  await expect(ways.getByRole("link", { name: m.Scan.wayLabel })).toBeVisible();
  await expectNoAxeViolations(page);
  await ways.getByRole("link", { name: m.Scan.wayType }).click();
  await expect(
    page.getByRole("tab", { name: m.Scan.tabs.type }),
  ).toHaveAttribute("aria-selected", "true");
});

test("a code that cannot be used offers the other two ways on the scan screen", async ({
  page,
}) => {
  await stubApi(page);
  await page.goto("/en/scan");
  await page.getByRole("tab", { name: m.Scan.tabs.type }).click();
  // A German PZN is a national code, not a GTIN.
  await page.getByLabel(m.Scan.typeLabel).fill("1234567");
  await page.getByRole("button", { name: m.Scan.submit, exact: true }).click();
  // The page's own alert (Next.js also keeps a route announcer with role "alert").
  await expect(page.locator("#content").getByRole("alert")).toContainText(
    m.Scan.nationalCode,
  );
  await page
    .getByTestId("other-ways")
    .getByRole("button", { name: m.Scan.wayLabel })
    .click();
  await expect(
    page.getByRole("tab", { name: m.Scan.tabs.label }),
  ).toHaveAttribute("aria-selected", "true");
});

for (const [name, init] of [
  [
    "camera permission refused",
    () => {
      navigator.mediaDevices.getUserMedia = () =>
        Promise.reject(new DOMException("refused", "NotAllowedError"));
    },
  ],
  [
    "no camera",
    () => {
      Object.defineProperty(navigator, "mediaDevices", { value: undefined });
    },
  ],
] as const)
  test(`label panel, ${name}: said plainly, the photo picker and typing stay`, async ({
    page,
  }) => {
    await page.addInitScript(init);
    await stubApi(page);
    await page.goto("/en/scan#label");
    await page.getByRole("button", { name: m.Scan.ocr.camera }).click();
    await expect(page.getByTestId("label-camera-unavailable")).toHaveText(
      m.Scan.ocr.cameraDenied,
    );
    await expect(page.getByLabel(m.Scan.ocr.pick)).toBeEnabled();
    await expectNoAxeViolations(page);
    await expectTouchTargets(page);
    await shot(page, `label-${name.replaceAll(" ", "-")}-en`);
    // The code tab says the same and offers the other ways.
    await page.getByRole("tab", { name: m.Scan.tabs.code }).click();
    await page.getByRole("button", { name: m.Scan.startCamera }).click();
    await expect(page.getByText(m.Scan.cameraDenied)).toBeVisible();
    await page
      .getByTestId("other-ways")
      .getByRole("button", { name: m.Scan.wayType })
      .click();
    await expect(page.getByLabel(m.Scan.typeLabel)).toBeVisible();
  });

test("label panel, reading failed: said plainly, typing offered", async ({
  page,
  browser,
}) => {
  test.setTimeout(120_000);
  await stubApi(page);
  await page.route("**/vendor/tesseract/**", (r) => r.abort());
  await page.goto("/en/scan#label");
  await pick(page, await label(browser, GERMAN_BOX));
  await expect(page.getByText(m.Scan.ocr.failed)).toBeVisible({
    timeout: 90_000,
  });
  await expectNoAxeViolations(page);
  await shot(page, "label-failed-en");
  await page.getByRole("button", { name: m.Scan.wayType }).click();
  await expect(page.getByLabel(m.Scan.typeLabel)).toBeVisible();
});

test("label panel, nothing recognised and no ingredient recognised", async ({
  page,
  browser,
}) => {
  test.setTimeout(180_000);
  const seen = await stubApi(page);
  await page.goto("/en/scan#label");
  await pick(page, await label(browser, []));
  await expect(page.getByText(m.Scan.ocr.none)).toBeVisible({
    timeout: 90_000,
  });
  await expectNoAxeViolations(page);
  await shot(page, "label-none-en");

  // Text, but no ingredient of the device list: the words are open to tap, nothing is guessed.
  await pick(page, await label(browser, ["Zentavorlu 20 mg", "28 tablets"]));
  await expect(page.getByTestId("label-no-ingredient")).toHaveText(
    m.Scan.ocr.noIngredient,
    { timeout: 90_000 },
  );
  await expect(page.getByTestId("label-candidate")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Zentavorlu" })).toBeVisible();
  expect(seen).toHaveLength(0);
  await expectNoAxeViolations(page);
  await expectTouchTargets(page);
  await shot(page, "label-no-ingredient-en");
});

// The candidates in every language, alternating themes (en in both).
for (const [locale, theme] of [
  ["en", "glass"],
  ["tr", "two-faces"],
  ["de", "glass"],
  ["fr", "two-faces"],
  ["es", "glass"],
] as const)
  test(`label candidates: ${locale}, ${theme}`, async ({ page, browser }) => {
    test.setTimeout(180_000);
    const s = messages[locale].Scan;
    await useTheme(page, theme);
    const seen = await stubApi(page);
    await page.goto(`/${locale}/scan#label`);
    await pick(page, await label(browser, GERMAN_BOX), locale);
    const candidates = page.getByTestId("label-candidate");
    await expect(candidates).toHaveCount(2, { timeout: 90_000 });
    await expect(
      page.getByRole("heading", { name: s.ocr.candidatesTitle }),
    ).toBeVisible();
    await expect(page.getByText(s.ocr.candidatesIntro)).toBeVisible();
    // Strongest first (ingredient-match.ts): the exact name, then the name joined to its salt.
    await expect(candidates.nth(0)).toContainText("Hydrochlorothiazid");
    await expect(candidates.nth(0)).toHaveAttribute("data-strength", "exact");
    await expect(candidates.nth(1)).toContainText("Ambroxolhydrochlorid");
    expect(seen).toHaveLength(0);
    await expectNoAxeViolations(page);
    await expectNoHorizontalScroll(page);
    await expectTouchTargets(page);
    await shot(page, `label-candidates-${locale}-${theme}`);
  });

// Recall check (recall-check Req 5-6): the notice on the medicine list and on the confirm screen
// (the scan result). The API is stubbed with the answer the API tests produce
// (src/recall/fixtures/check.json; invented records). C1-C3 in five locales × two themes; the
// lot of the box never leaves the page; nothing found, error with retry, demo mode with no
// request. Screenshots when RECALL_SHOTS_DIR is set.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { reassurance } from "../src/i18n/reassurance";

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
const sample = read("../src/recall/fixtures/check.json");
const none = { ...sample, matches: [], total_matches: 0 };
const ohio = read("../src/demo/fixtures/ohio.json");
const istanbul = read("../src/demo/fixtures/istanbul.json");
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../messages/${l}.json`)]),
);
const SHOTS = process.env.RECALL_SHOTS_DIR;
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

// NDC 99999-123-30 (invented) as an NDC GTIN; the box carries lot AB-1234.
const GTIN = "00399999123303";
const LOT = "AB-1234";
const usResolution = {
  ...ohio.items[0].resolution,
  candidates: [
    {
      ...ohio.items[0].resolution.candidates[0],
      matched_by: "ndc_gtin",
      product_name: "Exampletine 10 mg tablets (invented)",
      brand_name: "Exampletine 10 mg tablets (invented)",
      packages: [{ ndc_published: "99999-123-30", ndc11: "99999012330" }],
    },
  ],
};
const usItem = {
  id: "us-1",
  sourceKey: { kind: "scan", content: `(01)${GTIN}(17)270630` },
  datasetVersion: usResolution.dataset_version,
  candidate: usResolution.candidates[0],
  choices: [],
  started: "2025-03",
  boxName: "Exampletine 10 mg tablets (invented)",
  needsConfirmation: false,
  lot: LOT,
};
const trItem = {
  id: "tr-1",
  sourceKey: istanbul.items[2].sourceKey,
  datasetVersion: istanbul.items[2].resolution.dataset_version,
  candidate: istanbul.items[2].resolution.candidates[0],
  choices: istanbul.items[2].choices,
  started: null,
  boxName: "Turkish box (invented)",
  needsConfirmation: false,
};

const seed = (page: Page, items: unknown[]) =>
  page.addInitScript(
    (list) =>
      localStorage.setItem(
        "janus.v1.list",
        JSON.stringify({ v: 1, items: list }),
      ),
    items,
  );
const recallBodies = (seen: { url(): string; postDataJSON(): unknown }[]) =>
  seen
    .filter((r) => r.url().endsWith("/api/recalls/check"))
    .map((r) => r.postDataJSON());

async function shot(page: Page, name: string, project: string) {
  if (!SHOTS) return;
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({
    path: join(SHOTS, `${name}-${project}.png`),
    fullPage: true,
  });
}

for (const locale of locales)
  for (const theme of THEMES)
    test(`medicine list: recall notices, ${locale}, ${theme}`, async ({
      page,
    }, info) => {
      const m = messages[locale].Recall;
      await useTheme(page, theme);
      await seed(page, [usItem, trItem]);
      const requests = recordRequests(page);
      const seen = await stubApi(page, {
        "/recalls/check": { body: sample },
      });
      await page.goto(`/${locale}/medicines`);
      const notices = page.getByTestId("recall-notice");
      await expect(notices).toHaveCount(3);

      // The lot of the box is listed in the first record only; the title says so.
      await expect(notices.nth(0)).toHaveAttribute("data-lot", "listed");
      await expect(notices.nth(0)).toContainText(m.title.lot);
      await expect(notices.nth(0)).toContainText("D-0001-2026");
      await expect(notices.nth(0)).toContainText(
        "Failed Dissolution Specifications",
      );
      await expect(notices.nth(0)).toContainText(m.advice);
      // A terminated recall is labelled with its date; a lot that is not listed keeps the notice.
      await expect(notices.nth(1)).toHaveAttribute("data-lot", "not_listed");
      await expect(notices.nth(1)).toContainText(m.title.product);
      await expect(notices.nth(1).getByTestId("recall-status")).toContainText(
        "2025",
      );
      await expect(notices.nth(2)).toContainText(m.ndc.product);
      await expect(
        notices.nth(0).getByRole("link", { name: m.openRecord }),
      ).toHaveAttribute("href", sample.matches[0].record_url);
      await expect(
        notices.nth(0).getByRole("link", { name: m.search }),
      ).toHaveAttribute("href", sample.source.search_url);
      // One request, for the US item only, with the NDC and nothing else.
      expect(recallBodies(seen)).toEqual([{ ndc: "99999012330" }]);
      for (const r of requests) {
        expect(r.url()).not.toContain("1234");
        expect(r.postData() ?? "").not.toMatch(/AB-?1234/i);
      }

      await expect(page.getByTestId("disclaimer")).toHaveText(
        messages[locale].Disclaimer.text,
      );
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      const text = (await page.locator("body").innerText()).replace(
        /Failed Dissolution[^\n]*|Labeling:[^\n]*|Presence of Foreign[^\n]*/g,
        "",
      );
      expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
      await shot(page, `list-${locale}-${theme}`, info.project.name);

      // The folded record text opens and stays inside the page.
      await notices.nth(2).getByText(m.details).click();
      await expect(notices.nth(2)).toContainText(m.lotTextCut);
      await expectNoHorizontalScroll(page);
      await expectNoAxeViolations(page);
      await shot(page, `list-open-${locale}-${theme}`, info.project.name);
    });

for (const locale of locales)
  test(`nothing found is not a clearance, ${locale}`, async ({
    page,
  }, info) => {
    await seed(page, [usItem]);
    await stubApi(page, { "/recalls/check": { body: none } });
    await page.goto(`/${locale}/medicines`);
    const line = page.getByTestId("recall-none");
    await expect(line).toBeVisible();
    await expect(page.getByTestId("recall-notice")).toHaveCount(0);
    const text = await line.innerText();
    expect(text).toMatch(/2026/); // the data date
    expect(text).toContain(messages[locale].Common.region.US);
    expect(findForbiddenPhrases(text, reassurance[locale])).toEqual([]);
    expect(text).not.toContain("1234");
    await line.getByText(messages[locale].Recall.about).click();
    await expect(line).toContainText(String(sample.source.records));
    const opened = await line.innerText();
    expect(findForbiddenPhrases(opened, reassurance[locale])).toEqual([]);
    expect(findForbiddenPhrases(opened, forbiddenPhrases[locale])).toEqual([]);
    await expectNoAxeViolations(page);
    await expectNoHorizontalScroll(page);
    await shot(page, `none-${locale}`, info.project.name);
  });

test("error with a retry, then the answer", async ({ page }, info) => {
  await seed(page, [usItem]);
  let calls = 0;
  await stubApi(page, {
    "/recalls/check": () =>
      ++calls === 1
        ? { status: 503, body: { error: "recalls_unavailable" } }
        : { body: sample },
  });
  await page.goto("/en/medicines");
  const error = page.getByTestId("recall-error");
  await expect(error).toContainText(
    "Janus could not check the FDA recall records. The recall records are not available right now. Please try again later.",
  );
  await expect(page.getByTestId("recall-notice")).toHaveCount(0);
  await expectNoAxeViolations(page);
  await shot(page, "error", info.project.name);
  await error.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByTestId("recall-notice")).toHaveCount(3);
  expect(calls).toBe(2);
});

test("scan result: the lot stays on the device from the code to the list", async ({
  page,
}, info) => {
  const requests = recordRequests(page);
  const seen = await stubApi(page, {
    "/resolve/scan": { body: usResolution },
    "/recalls/check": { body: sample },
  });
  await page.goto("/en/scan");
  await page.getByRole("tab", { name: "Type name or NDC" }).click();
  await page
    .getByLabel("Name of the medicine or NDC")
    .fill(`(01)${GTIN}(17)270630(10)${LOT}`);
  await page.getByRole("button", { name: "Look up", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Confirm the medicine" }),
  ).toBeVisible();
  // Nothing is checked before the person chooses a candidate.
  await expect(page.getByTestId("recall-notice")).toHaveCount(0);
  expect(recallBodies(seen)).toEqual([]);
  await page.getByRole("button", { name: "This one" }).click();
  const notices = page.getByTestId("recall-notice");
  await expect(notices).toHaveCount(3);
  await expect(notices.nth(0)).toContainText(
    "This product and lot appear in an FDA recall record",
  );
  await expect(notices.nth(0).getByTestId("recall-lot")).toHaveText(
    `The automated reading found the lot on your box (${LOT}) in the lot text of the record.`,
  );
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await shot(page, "confirm", info.project.name);

  await page.getByRole("button", { name: "Add to my medicines" }).click();
  await expect(
    page.getByRole("heading", { name: "Exampletine 10 mg tablets (invented)" }),
  ).toBeVisible();
  await expect(page.getByTestId("recall-notice").first()).toHaveAttribute(
    "data-lot",
    "listed",
  );
  // The lot is in the browser's list, and in no request.
  const stored = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("janus.v1.list") ?? "{}"),
  );
  expect(stored.items[0].lot).toBe(LOT);
  expect(stored.items[0].sourceKey).toEqual({
    kind: "scan",
    content: `(01)${GTIN}(17)270630`,
  });
  const scans = seen.filter((r) => r.url().endsWith("/api/resolve/scan"));
  expect(scans.map((r) => r.postDataJSON())).toEqual([
    { content: `(01)${GTIN}(17)270630` },
  ]);
  // Asked once: the answer of the confirm screen is reused on the list.
  expect(recallBodies(seen)).toEqual([{ ndc: "99999012330" }]);
  const origin = new URL(page.url()).origin;
  for (const r of requests) {
    expect(r.url().startsWith(origin) || /^(data|blob):/.test(r.url())).toBe(
      true,
    );
    expect(r.url()).not.toContain("1234");
    expect(r.postData() ?? "").not.toMatch(/AB-?1234/i);
  }
});

test("demo mode: no recall request, one line that says why", async ({
  page,
}) => {
  const seen = await stubApi(page);
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "ohio"),
  );
  await page.goto("/en/medicines");
  await expect(page.getByTestId("recall-demo")).toHaveText(
    "The recall check does not run in the demo: the demo products are invented.",
  );
  await expect(page.getByTestId("recall-notice")).toHaveCount(0);
  await expect(page.getByTestId("recall-none")).toHaveCount(0);
  expect(recallBodies(seen)).toEqual([]);
});

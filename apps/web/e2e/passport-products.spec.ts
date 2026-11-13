// medication-passport task 19.1: the product-list screen in a real browser. Axe (WCAG 2.2 A/AA),
// no horizontal scroll, 44 px targets and the disclaimer at 375 px and 1280 px (by project), in
// both themes and every locale; the Cologne demo (recorded answer, no request to the API); the
// live states with a stubbed API (flags, paging, target change, error with retry); screenshots.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { productsFor } from "../src/test/fixtures/passport";
import type { ProductsIn } from "../src/passport/products";

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

const SHOTS = process.env.PASSPORT_SHOTS;
const read = (f: string) =>
  JSON.parse(readFileSync(join(import.meta.dirname, "../src", f), "utf8"));
const istanbul = read("demo/fixtures/istanbul.json");
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
const AMLODIPINE = "demo-cologne-passport-5";

async function checks(page: Page) {
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, {
    timeout: 15_000,
  });
  await expect(page.getByTestId("disclaimer")).toBeVisible();
  await expect(page.getByTestId("products-caution")).toBeVisible();
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
}

async function shot(page: Page, name: string, project: string) {
  if (!SHOTS) return;
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({
    path: join(SHOTS, `passport-products-${name}-${project}.png`),
    fullPage: true,
  });
}

const cologne = (page: Page) =>
  page.addInitScript(() => sessionStorage.setItem("janus.v1.demo", "cologne"));

for (const theme of THEMES) {
  test(`Cologne demo, from the box to the product list, ${theme}`, async ({
    page,
  }, info) => {
    await useTheme(page, theme);
    await cologne(page);
    const requests = recordRequests(page);
    await page.goto(`/en/passport/item#${AMLODIPINE}`);
    await page
      .getByRole("link", {
        name: "Products with the same active ingredient in another country",
      })
      .click();
    await expect(page).toHaveURL(/\/en\/passport\/products#/);
    await checks(page);
    await expect(page.getByTestId("demo-label")).toBeVisible();
    await expect(
      page.getByText(
        "Confirm with a pharmacist or doctor before you take a different product.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("radio", { name: "France" })).toBeChecked();
    await expect(page.getByTestId("listed-product").first()).toBeVisible();
    await expect(
      page.getByText(/^Recorded answer of \d{4}-\d{2}-\d{2}\.$/),
    ).toBeVisible();
    await expect(
      page.getByText("the BDPM does not endorse Janus"),
    ).toBeVisible();
    await shot(page, `fr-${theme}`, info.project.name);

    // Keyboard: the country choice is a radio group; arrow keys move it.
    await page.getByRole("radio", { name: "France" }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("radio", { name: "Spain" })).toBeChecked();
    await expect(page.getByTestId("listed-product").first()).toBeVisible();
    await page.getByRole("radio", { name: "United States" }).check();
    await expect(page.getByText("Not an FDA endorsement.")).toBeVisible();
    await checks(page);
    await shot(page, `us-${theme}`, info.project.name);

    expect(
      requests
        .filter((r) => new URL(r.url()).pathname.startsWith("/api/"))
        .map((r) => r.url()),
    ).toEqual([]);
  });

  for (const locale of locales)
    test(`product list, ${locale}, ${theme}`, async ({ page }, info) => {
      await useTheme(page, theme);
      await cologne(page);
      await page.goto(`/${locale}/passport/products#${AMLODIPINE}`);
      await checks(page);
      const p = messages[locale].Passport.products;
      await expect(page.getByText(p.caution.confirm)).toBeVisible();
      await expect(page.getByText(p.caution.noDosing)).toBeVisible();
      await expect(page.getByText(p.notes.automated)).toBeVisible();
      // the first page of the bundled file: some rows, never more than one page of eight
      await expect(page.getByTestId("listed-product").first()).toBeVisible();
      expect(
        await page.getByTestId("listed-product").count(),
      ).toBeLessThanOrEqual(8);
      await shot(page, `${locale}-${theme}`, info.project.name);
      // Another demo box: the page renders its answer (rows or a statement about the data).
      await page.goto(`/${locale}/passport/products#demo-cologne-passport-2`);
      await page.reload();
      await checks(page);
      await expect(
        page
          .getByTestId("listed-product")
          .first()
          .or(page.locator('[data-status="not_present"]')),
      ).toBeVisible();
    });
}

/** A stored list with one Turkish box from the Istanbul fixture (the person's own list). */
async function ownList(page: Page) {
  const it = istanbul.items[2];
  const res = it.resolution;
  await page.addInitScript(
    (item) =>
      localStorage.setItem(
        "janus.v1.list",
        JSON.stringify({ v: 1, items: [item] }),
      ),
    {
      id: "own-1",
      sourceKey: it.sourceKey,
      datasetVersion: res.dataset_version,
      candidate: res.candidates[0],
      choices: it.choices,
      started: it.started,
      boxName: "Own box 1000",
      needsConfirmation: false,
    },
  );
}

type Body = { target: string; offset: number; ingredients: unknown[] };
/** A first page of the synthetic list for a single ingredient (51 rows in all, eight shown). */
const answer = (target: string) =>
  structuredClone(
    productsFor({
      ingredients: [{ key: "Q412666" }],
      target: target as ProductsIn["target"],
      offset: 0,
      limit: 8,
    }),
  );

test("own list: flags, paging and target change with keys and codes only", async ({
  page,
}, info) => {
  await ownList(page);
  const bodies: Body[] = [];
  await stubApi(page, {
    "/passport/products": (body) => {
      const b = body as Body;
      bodies.push(b);
      const out = answer(b.target);
      out.total = 12;
      out.offset = b.offset;
      out.products = out.products.slice(0, b.offset === 0 ? 8 : 4);
      if (b.offset === 0) {
        out.products[0]!.strength = "different";
        out.products[1]!.dose_form = "different";
        out.products[1]!.dose_form_group = "oral_liquid";
      }
      if (b.target === "eu_es_cima")
        for (const p of out.products) {
          p.strength = "unknown";
          p.strength_reason = "not_known_in_source";
        }
      return { body: out };
    },
  });
  await page.goto("/en/passport/products#own-1");
  await checks(page);
  await expect(page.getByTestId("listed-product")).toHaveCount(8);
  await expect(page.getByTestId("different")).toHaveCount(2);
  await expect(page.getByTestId("listed-product").first()).toContainText(
    "Different listed strength:",
  );
  await expect(page.getByTestId("listed-product").nth(1)).toContainText(
    "Different form group (Liquid taken by mouth).",
  );
  await expect(page.getByText(/^Showing 8 of 12 rows\./)).toBeVisible();
  await shot(page, "flags", info.project.name);
  await page.getByRole("button", { name: "Show more" }).click();
  await expect(page.getByTestId("listed-product")).toHaveCount(12);
  await expect(page.getByRole("button", { name: "Show more" })).toHaveCount(0);
  await page.getByRole("radio", { name: "Spain" }).check();
  await expect(
    page.getByText("Source: AEMPS, Nomenclátor de prescripción"),
  ).toBeVisible();
  await expect(page.getByTestId("listed-product").first()).toContainText(
    "Strength not compared:",
  );
  await checks(page);
  expect(bodies.map((b) => [b.target, b.offset])).toEqual([
    ["eu_fr_bdpm", 0],
    ["eu_fr_bdpm", 8],
    ["eu_es_cima", 0],
  ]);
  for (const b of bodies) {
    expect(Object.keys(b).sort()).toEqual([
      "ingredients",
      "limit",
      "offset",
      "target",
    ]);
    expect(JSON.stringify(b)).not.toContain("Own box");
  }
});

test("own list: an unavailable service offers a retry, never 'not found'", async ({
  page,
}, info) => {
  await ownList(page);
  let fail = true;
  await stubApi(page, {
    "/passport/products": (body) =>
      fail
        ? { status: 503, body: { error: "passport_unavailable" } }
        : { body: answer((body as Body).target) },
  });
  await page.goto("/en/passport/products#own-1");
  await expect(
    page.getByText("The products could not be looked up now."),
  ).toBeVisible();
  await checks(page);
  await expect(page.getByText(/not found/i)).toHaveCount(0);
  await shot(page, "error", info.project.name);
  fail = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByTestId("listed-product")).toHaveCount(8);
});

test("own list: Italy and Canada as targets show source, data date and attribution", async ({
  page,
}, info) => {
  await ownList(page);
  const bodies: Body[] = [];
  const dates = { eu_it_aifa: "2026-11-10", ca_dpd: "2026-11-02" } as const;
  const sources = {
    eu_it_aifa: { id: 5, region: "EU", country: "IT", attribution: "aifa" },
    ca_dpd: { id: 6, region: "CA", country: null, attribution: "dpd" },
  } as const;
  await stubApi(page, {
    "/passport/products": (body) => {
      const b = body as Body;
      bodies.push(b);
      const out = answer("eu_fr_bdpm");
      const s = sources[b.target as keyof typeof sources];
      if (s) {
        out.source = {
          ...out.source,
          source: s.id,
          source_id: b.target as ProductsIn["target"],
          region: s.region,
          country: s.country,
          attribution: s.attribution,
          snapshot_date: dates[b.target as keyof typeof dates],
        };
      }
      out.total = 8;
      out.products = out.products.slice(0, 8);
      return { body: out };
    },
  });
  await page.goto("/en/passport/products#own-1");
  await checks(page);
  await page.getByRole("radio", { name: "Italy" }).check();
  await expect(
    page.getByText(/Source: Italian Medicines Agency \(AIFA\)/),
  ).toContainText("data as of Nov 10, 2026");
  await expect(page.getByText(/CC BY 4\.0/).first()).toBeVisible();
  await checks(page);
  await shot(page, "italy", info.project.name);
  await page.getByRole("radio", { name: "Canada" }).check();
  await expect(
    page.getByText(/Source: Health Canada, Drug Product Database/),
  ).toContainText("data as of Nov 2, 2026");
  await expect(page.getByText(/Open Government Licence/).first()).toBeVisible();
  await checks(page);
  await shot(page, "canada", info.project.name);
  expect(bodies.map((b) => b.target)).toEqual([
    "eu_fr_bdpm",
    "eu_it_aifa",
    "ca_dpd",
  ]);
});

// fhir-export Req 6.3: the FHIR file is built and saved in the browser (demo session), holds one
// MedicationStatement per item, no box names unless ticked, and nothing is sent. The card passes
// C1–C3 at both viewports (projects), in both themes and every locale (E2E_LOCALES respected).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { fhirSchemaErrors } from "../src/fhir/schema/validate";
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

const read = (...p: string[]) =>
  JSON.parse(readFileSync(join(import.meta.dirname, ...p), "utf8"));
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read("../messages", `${l}.json`)]),
);
const istanbul = read("../src/demo/fixtures/istanbul.json") as {
  items: { boxName: string }[];
};
const BOX_NAMES = istanbul.items.map((i) => i.boxName);

const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

async function open(page: Page, locale: string) {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  await page.goto(`/${locale}/medicines`);
  await page.waitForLoadState("networkidle");
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, {
    timeout: 15_000,
  });
  const card = page.getByTestId("fhir-export");
  await expect(card).toBeVisible();
  return card;
}

async function download(page: Page) {
  const card = page.getByTestId("fhir-export");
  const [file] = await Promise.all([
    page.waitForEvent("download"),
    card.getByRole("button", { name: messages.en.Fhir.download }).click(),
  ]);
  const text = readFileSync((await file.path())!, "utf8");
  return { name: file.suggestedFilename(), json: JSON.parse(text), text };
}

test("download: a collection Bundle, one statement per item, no box names, nothing sent", async ({
  page,
}) => {
  const card = await open(page, "en");
  await expect(card.getByTestId("fhir-preview")).toHaveText(
    "9 medicines, 10 of 10 ingredients with a standard code (ATC, RxNorm)",
  );
  const requests = recordRequests(page);
  const { name, json, text } = await download(page);
  expect(name).toMatch(/^janus-medicines-\d{4}-(0[1-9]|1[0-2])\.fhir\.json$/);
  expect(json.resourceType).toBe("Bundle");
  expect(json.type).toBe("collection");
  // The file the browser saved is valid against the official R4 schema.
  expect(fhirSchemaErrors(json)).toEqual([]);
  expect(json.meta.security[0].code).toBe("HTEST");
  expect(json.entry).toHaveLength(9);
  expect(
    json.entry.map(
      (e: { resource: { resourceType: string } }) => e.resource.resourceType,
    ),
  ).toEqual(Array(9).fill("MedicationStatement"));
  for (const box of BOX_NAMES) expect(text).not.toContain(box);
  await expect(card.getByRole("status")).toHaveText(
    messages.en.Fhir.saved.replace("{file}", name),
  );

  // Ticked: every box name is in the file, in list order.
  await card
    .getByRole("checkbox", { name: messages.en.Fhir.includeNames })
    .check();
  const ticked = await download(page);
  expect(fhirSchemaErrors(ticked.json)).toEqual([]);
  ticked.json.entry.forEach((e: { resource: object }, i: number) =>
    expect(JSON.stringify(e.resource)).toContain(BOX_NAMES[i]),
  );
  // Nothing is sent while building and saving: no API call, no request with a body, nothing to
  // another origin. (Next.js may prefetch its own pages and chunks by GET; those carry no data.)
  const origin = new URL(page.url()).origin;
  expect(
    requests
      .filter(
        (r) => !r.url().startsWith("blob:") && !r.url().startsWith("data:"),
      )
      .filter(
        (r) =>
          r.method() !== "GET" ||
          r.postData() !== null ||
          new URL(r.url()).origin !== origin ||
          new URL(r.url()).pathname.startsWith("/api/"),
      )
      .map((r) => `${r.method()} ${r.url()}`),
  ).toEqual([]);
});

for (const theme of THEMES)
  for (const locale of locales)
    test(`card, ${locale}, ${theme}`, async ({ page }) => {
      await useTheme(page, theme);
      const requests = recordRequests(page);
      const card = await open(page, locale);
      const m = messages[locale].Fhir;
      await expect(card.getByRole("heading", { name: m.title })).toBeVisible();
      await expect(card).toContainText(m.notSent);
      await expect(card).toContainText(m.notChecked);
      await expect(card).toContainText(m.demo);
      await expect(
        card.getByRole("checkbox", { name: m.includeNames }),
      ).not.toBeChecked();
      await card.scrollIntoViewIfNeeded();
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      const text = await card.innerText();
      expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
      if (theme === "glass")
        expect(findForbiddenPhrases(text, themeWords[locale])).toEqual([]);
      // Demo mode: nothing reaches the API.
      expect(
        requests.filter((r) => new URL(r.url()).pathname.startsWith("/api/")),
      ).toEqual([]);
    });

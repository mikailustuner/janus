// C6 (checkpoint 1): Istanbul → results (row 5 probable) → finding detail (evidence, FAERS pair)
// → Collective Memory → note in two languages → PDF downloaded (%PDF, the disclaimer in its text).
// C4 for the same flow: no request to the API at all, every request to the own origin.
import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { pdfText } from "./pdf-text";
import { recordRequests } from "./helpers";

test("demo flow end to end, with no API request", async ({ page }) => {
  const requests = recordRequests(page);
  await page.goto("/en");
  await page.getByRole("link", { name: "Try the demo" }).click();
  await page.getByRole("button", { name: "Open the Istanbul patient" }).click();
  await expect(
    page.getByRole("heading", { name: "Amlodis Plus 10/20 (demo)" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Check for patterns" }).click();

  const row5 = page.locator('[data-testid="finding"][data-rule="pipc:5"]');
  await expect(row5).toBeVisible();
  await expect(row5).toContainText("Probable · 5 months apart");
  await expect(row5).toContainText(
    "Calcium channel blocker → Peripheral edema → Diuretic",
  );
  await expect(page.getByTestId("abrupt-stop")).toHaveCount(2);

  await row5.getByRole("link", { name: "Evidence and reports" }).click();
  await expect(page.getByTestId("integrity-line")).toContainText(
    "No retracted source was used.",
  );
  await expect(page.getByTestId("pair-panel")).toContainText("424 reports");
  await expect(page.getByTestId("ci-bar")).toBeVisible();

  await page.getByRole("link", { name: "Reports for the whole list" }).click();
  await expect(page.getByTestId("memory-combination")).toBeVisible();
  await expect(page.getByTestId("memory-regions")).toBeVisible();
  await expect(page.getByTestId("memory-contributions")).toContainText(
    "Hidden under 20, noise added.",
  );

  await page.goto("/en/note");
  await page.getByRole("button", { name: "Make the note" }).click();
  const paper = page.getByTestId("note-paper");
  await expect(paper).toContainText("Hekim için ilaç değerlendirme notu");
  await expect(paper).toContainText("Amlodis Plus 10/20 (demo)");
  await expect(paper).toContainText("Demo · synthetic patient");
  await expect(page.getByText("Side by side")).toBeVisible();

  const download = page.waitForEvent("download");
  await page.getByTestId("download-pdf").click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^janus-note-\d{4}-\d{2}\.pdf$/);
  const pdf = readFileSync((await file.path())!);
  expect(pdf.subarray(0, 4).toString()).toBe("%PDF");
  const { text, pages } = pdfText(pdf);
  expect(pages).toBeGreaterThanOrEqual(1);
  expect(text).toContain("Janus bilgi sağlar, tıbbi tavsiye vermez.");
  expect(text).toContain("Amlodis Plus 10/20 (demo)");
  expect(text).toContain("Demo · synthetic patient");

  const api = requests.filter((r) =>
    new URL(r.url()).pathname.startsWith("/api/"),
  );
  expect(api.map((r) => r.url())).toEqual([]);
  const origin = new URL(page.url()).origin;
  expect(
    requests
      .filter(
        (r) => !r.url().startsWith(origin) && !/^(data|blob):/.test(r.url()),
      )
      .map((r) => r.url()),
  ).toEqual([]);
});

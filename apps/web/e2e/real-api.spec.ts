// Local only (E2E_REAL_API=1, the build pointing at a running API with note keys, consent
// versions and a donation region): the outcome loop and a donation end to end against the real
// API — QR opt-in, the doctor page with the issued token, withdrawal, donation and deletion.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

test.skip(!process.env.E2E_REAL_API, "needs the real local API");

const fx = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "../src/demo/fixtures/istanbul.json"),
    "utf8",
  ),
);
const listDoc = {
  v: 1,
  items: fx.items.map(
    (
      it: {
        resolution: { dataset_version: string; candidates: unknown[] };
        sourceKey: unknown;
        boxName: string;
        started: string | null;
      },
      i: number,
    ) => ({
      id: `x${i}`,
      sourceKey: it.sourceKey,
      datasetVersion: it.resolution.dataset_version,
      candidate: it.resolution.candidates[0],
      choices: [],
      started: it.started,
      boxName: it.boxName,
      needsConfirmation: false,
    }),
  ),
};

test("outcome loop and donation on the real API", async ({ page }, info) => {
  test.skip(info.project.name !== "phone", "once");
  test.setTimeout(120_000);
  await page.addInitScript((doc) => {
    if (!localStorage.getItem("janus.v1.list")) {
      localStorage.setItem("janus.v1.list", JSON.stringify(doc));
      localStorage.setItem(
        "janus.v1.settings",
        JSON.stringify({ v: 1, userRegion: "TR" }),
      );
    }
  }, listDoc);
  await page.goto("/en/results");
  await expect(
    page.locator('[data-testid="finding"][data-rule="pipc:5"]'),
  ).toBeVisible({ timeout: 30_000 });
  await page.goto("/en/note");
  await page.getByRole("button", { name: "Make the note" }).click();
  await expect(page.getByTestId("note-paper")).toBeVisible({ timeout: 30_000 });
  await page
    .getByLabel("I have read this and want the QR code on the note.")
    .check();
  await page.getByRole("button", { name: "Add the QR code" }).click();
  await expect(page.getByTestId("note-qr")).toBeVisible({ timeout: 30_000 });
  const token = await page.evaluate(
    () =>
      JSON.parse(localStorage.getItem("janus.v1.tokens")!).notes[0]
        .token as string,
  );
  expect(token.length).toBeGreaterThan(40);

  await page.goto(`/o#${token}`);
  await page.getByRole("radio").first().check();
  await page.getByRole("button", { name: /Gönder|Send/ }).click();
  await expect(page.getByTestId("doctor-sent")).toBeVisible();

  await page.goto("/en/note/withdraw");
  await page.getByRole("button", { name: "Withdraw" }).click();
  await expect(page.getByText(/^Withdrawn\./)).toBeVisible();
  expect(
    await page.evaluate(
      () => JSON.parse(localStorage.getItem("janus.v1.tokens")!).notes.length,
    ),
  ).toBe(0);

  await page.goto("/en/donate#event=peripheral_oedema");
  await page.getByLabel("amlodipine", { exact: true }).check();
  await page.getByLabel("Age band").selectOption("70");
  await page
    .getByLabel(
      "I explicitly agree to share the fields above as a donated report, without my name or contact details.",
    )
    .check();
  await page.getByTestId("donate-submit").click();
  const deletion = (
    await page.getByTestId("deletion-token").innerText()
  ).trim();
  expect(deletion).toMatch(/^jdt_/);
  await page
    .getByRole("button", { name: "Keep the token on this device" })
    .click();
  await page.goto("/en/donate/delete");
  await page.getByLabel("Deletion token").fill(deletion);
  await page.getByRole("button", { name: "Delete the donation" }).click();
  await expect(page.getByText("The donation was deleted.")).toBeVisible();
});

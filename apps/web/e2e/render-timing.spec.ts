// Req 25.3: a 15-item list shows its findings within 2 s of the evaluation response (rendering
// only; measured locally and recorded in design §16).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

const fx = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "../src/demo/fixtures/istanbul.json"),
    "utf8",
  ),
);
const items = Array.from({ length: 15 }, (_, i) => {
  const it = fx.items[i % fx.items.length];
  return {
    id: `x${i}`,
    sourceKey: it.sourceKey,
    datasetVersion: it.resolution.dataset_version,
    candidate: it.resolution.candidates[0],
    choices: [],
    started: it.started,
    boxName: `${it.boxName} ${i}`,
    needsConfirmation: false,
  };
});

test("15 items render their findings within 2 s of the response", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "phone", "once");
  await page.addInitScript(
    (doc) => localStorage.setItem("janus.v1.list", JSON.stringify(doc)),
    { v: 1, items },
  );
  let answered = 0;
  await page.route("**/api/cascades/evaluate", async (route) => {
    answered = Date.now();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(fx.evaluation),
    });
  });
  await page.goto("/en/results");
  await expect(page.getByTestId("finding")).toHaveCount(4);
  const ms = Date.now() - answered;
  console.log(`render 15 items: ${ms} ms after the response`);
  expect(ms).toBeLessThan(2000);
});

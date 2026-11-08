// Task 15.3: the stubbed live flow (type a TR code → confirm → since when → results) and the 409
// path (re-resolution by source key, one more evaluation). C4 for a real flow: every request goes
// to the own origin, no body is an image or larger than 8 KiB, the scan body is the code only.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { recordRequests, stubApi } from "./helpers";

const fixture = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "../src/demo/fixtures/istanbul.json"),
    "utf8",
  ),
);
const resolution = fixture.items[1].resolution;
const noPattern = {
  ...fixture.evaluation,
  findings: [],
  chains: [],
  item_warnings: [],
  statement: { code: "no_pattern_found", text: "canonical" },
};

test("live flow with a dataset change on the way", async ({ page }) => {
  const requests = recordRequests(page);
  let evaluations = 0;
  const seen = await stubApi(page, {
    "/resolve/scan": { body: resolution },
    "/cascades/evaluate": () =>
      ++evaluations === 1
        ? { status: 409, body: { error: "dataset_version_mismatch" } }
        : { body: noPattern },
  });
  await page.goto("/en/scan");
  await page.getByRole("tab", { name: "Type name or NDC" }).click();
  await page.getByLabel("Name of the medicine or NDC").fill("8690000000012");
  await page.getByRole("button", { name: "Look up", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Confirm the medicine" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add to my medicines" }).click();
  await expect(
    page.getByText("Please choose one medicine first."),
  ).toBeVisible();
  await page.getByRole("button", { name: "This one" }).click();
  await page.getByLabel("Name on the box").fill("ZZBOX my water tablet");
  await page.getByLabel("Don't know").uncheck();
  await page.getByLabel("Year").selectOption("2024");
  await page.getByRole("button", { name: "Add to my medicines" }).click();
  await expect(
    page.getByRole("heading", { name: "ZZBOX my water tablet" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Check for patterns" }).click();
  await expect(page.getByTestId("no-pattern")).toHaveText(
    "Janus found no pattern from its rule list. This does not mean your medicines are free of problems.",
  );
  expect(evaluations).toBe(2);
  const scans = seen.filter((r) => r.url().endsWith("/api/resolve/scan"));
  expect(scans).toHaveLength(2); // the second one re-resolves the item after the 409
  for (const r of scans)
    expect(r.postDataJSON()).toEqual({ content: "8690000000012" });
  const origin = new URL(page.url()).origin;
  for (const r of requests) {
    expect(r.url().startsWith(origin) || /^(data|blob):/.test(r.url())).toBe(
      true,
    );
    const body = r.postData() ?? "";
    expect(body.length).toBeLessThanOrEqual(8192);
    expect(body).not.toContain("ZZBOX");
    expect(r.headers()["content-type"] ?? "").not.toMatch(/^image\//);
  }
});

test("label photo: recognised on the device, nothing sent until a choice, the NDC chip sends the NDC only", async ({
  page,
  browser,
}) => {
  // A pharmacy label with personal lines, drawn and photographed in the browser.
  const painter = await browser.newPage({
    viewport: { width: 900, height: 360 },
  });
  await painter.setContent(
    `<body style="margin:0;background:#fff;font:34px/1.5 Arial;padding:24px">
      <div>PATIENT ZZJANE DOE</div><div>DONEPEZIL 10 MG TABLETS</div><div>NDC 0295-2680-01</div><div>DR ZZSMITH</div></body>`,
  );
  const png = await painter.screenshot();
  await painter.close();

  const seen = await stubApi(page, { "/resolve/ndc": { body: resolution } });
  test.setTimeout(120_000);
  await page.goto("/en/scan#label");
  await expect(
    page.getByRole("tab", { name: "Photo of label" }),
  ).toHaveAttribute("aria-selected", "true");
  await page
    .getByLabel("Choose a photo of the label")
    .setInputFiles({ name: "label.png", mimeType: "image/png", buffer: png });
  await expect(page.getByRole("button", { name: "DONEPEZIL" })).toBeVisible({
    timeout: 60_000,
  });
  expect(seen).toHaveLength(0); // recognised text is never sent as a whole
  // The demo NDC is recognised before any request (it opens the demo prompt).
  await page.getByRole("button", { name: /Look up NDC 0295-2680-01/ }).click();
  await expect(
    page.getByText("This is a Janus demo code. Open the demo?"),
  ).toBeVisible();
  expect(seen).toHaveLength(0);
});

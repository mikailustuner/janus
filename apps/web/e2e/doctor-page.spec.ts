// Task 17: the doctor page /o. P26 in the browser (token only in JSON bodies, nothing for a demo
// or a malformed fragment, no storage), the form and Send rule, error texts, C1–C2 at 375 px,
// and C5: the form is ready in < 3 s (median of 5 cold loads) on a phone profile with 4G
// throttling and CPU 4× slowdown, the form answer delayed 300 ms.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import {
  expectNoAxeViolations,
  expectNoHorizontalScroll,
  expectTouchTargets,
  recordRequests,
  stubApi,
} from "./helpers";

const fixture = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "../src/demo/fixtures/istanbul.json"),
    "utf8",
  ),
);
const TOKEN = "T".repeat(48);

test("posts the token only in JSON bodies and stores an answer", async ({
  page,
}) => {
  const requests = recordRequests(page);
  const seen = await stubApi(page, {
    "/outcomes/form": { body: fixture.doctorForm },
    "/outcomes": (body) => ({
      body: { stored: (body as { answers: unknown[] }).answers.length },
    }),
  });
  await page.goto(`/o#${TOKEN}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    fixture.doctorForm.texts.heading,
  );
  const send = page.getByRole("button", { name: /Gönder|Send/ });
  await expect(send).toBeDisabled();
  await page
    .getByLabel(fixture.doctorForm.options.assessment[0].text)
    .first()
    .check();
  await page
    .getByLabel(fixture.doctorForm.options.action[0].text)
    .first()
    .check(); // dose changed → which medicine
  await expect(send).toBeDisabled();
  await page
    .getByLabel(fixture.doctorForm.findings[0].action_on[0].text)
    .check();
  await expect(send).toBeEnabled();
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  await send.click();
  await expect(page.getByTestId("doctor-sent")).toBeVisible();
  const bodies = seen.map((r) => ({
    url: new URL(r.url()).pathname,
    body: r.postDataJSON(),
  }));
  expect(bodies[0]).toEqual({
    url: "/api/outcomes/form",
    body: { token: TOKEN },
  });
  expect(bodies[1]!.body.token).toBe(TOKEN);
  expect(bodies[1]!.body.answers).toEqual([
    {
      ref: 0,
      assessment: "confirmed",
      action: "dose_changed",
      action_on: "index",
    },
  ]);
  for (const r of requests)
    expect(r.url().includes(TOKEN) && !r.postData()?.includes(TOKEN)).toBe(
      false,
    );
  const stored = await page.evaluate(
    () =>
      JSON.stringify({ ...localStorage }) +
      JSON.stringify({ ...sessionStorage }),
  );
  expect(stored).not.toContain(TOKEN);
});

for (const [hash, text] of [
  ["#demo-istanbul", "Demo"],
  ["#not-a-token", "This link is not valid."],
] as const) {
  test(`sends nothing for ${hash}`, async ({ page }) => {
    const seen = await stubApi(page, {});
    await page.goto(`/o${hash}`);
    await expect(page.getByText(text).first()).toBeVisible();
    expect(seen).toHaveLength(0);
  });
}

test("words errors (token used)", async ({ page }) => {
  await stubApi(page, {
    "/outcomes/form": { status: 409, body: { error: "token_used" } },
  });
  await page.goto(`/o#${TOKEN}`);
  await expect(
    page.getByText("An answer was already sent for this note."),
  ).toBeVisible();
});

test("C5: the form is ready within 3 s on a throttled phone", async ({
  browser,
}, info) => {
  test.skip(info.project.name !== "phone", "phone profile only");
  // A timing check: run it on an otherwise idle machine (`playwright test -g C5 --workers=1`).
  test.setTimeout(120_000);
  const times: number[] = [];
  for (let i = 0; i < 5; i++) {
    const context = await browser.newContext({
      viewport: { width: 375, height: 812 },
    });
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    await cdp.send("Network.enable");
    await cdp.send("Network.emulateNetworkConditions", {
      offline: false,
      latency: 150,
      downloadThroughput: (1.6 * 1024 * 1024) / 8,
      uploadThroughput: (750 * 1024) / 8,
    });
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await page.route("**/api/outcomes/form", async (route) => {
      await new Promise((r) => setTimeout(r, 300));
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(fixture.doctorForm),
      });
    });
    await page.goto(`/o#${TOKEN}`);
    await page.waitForFunction(
      () => performance.getEntriesByName("janus:form-ready").length > 0,
      null,
      { timeout: 15_000 },
    );
    times.push(
      await page.evaluate(
        () => performance.getEntriesByName("janus:form-ready")[0]!.startTime,
      ),
    );
    await context.close();
  }
  times.sort((a, b) => a - b);
  const median = times[2]!;
  console.log(
    `C5 doctor page form-ready ms: ${times.map(Math.round).join(", ")} (median ${Math.round(median)})`,
  );
  expect(median).toBeLessThan(3000);
});

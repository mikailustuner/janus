// Task 19.1: loading, empty, error and long-content states rendered from stubs (design §9 table).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { expectNoHorizontalScroll, stubApi } from "./helpers";

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
      boxName: `${it.boxName} Langwortzusammensetzungsbeispiel`,
      needsConfirmation: false,
    }),
  ),
};

async function withList(page: Page) {
  await page.addInitScript(
    (doc) => localStorage.setItem("janus.v1.list", JSON.stringify(doc)),
    listDoc,
  );
}

test("empty: no medicines yet", async ({ page }) => {
  await page.goto("/en/medicines");
  await expect(page.getByText("No medicines yet.")).toBeVisible();
  await page.goto("/en/results");
  await expect(page.getByText("Add medicines to check them.")).toBeVisible();
  await page.goto("/en/note");
  await expect(
    page.getByText("Add medicines and check them to make a note."),
  ).toBeVisible();
});

test("loading, then results; error: the check is not available (no findings, no rule-3 sentence)", async ({
  page,
}) => {
  await withList(page);
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  await page.route("**/api/cascades/evaluate", async (route) => {
    await gate;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: "cascades_unavailable" }),
    });
  });
  await page.goto("/en/results");
  await expect(page.getByText("Checking the medicines…")).toBeVisible();
  release();
  await expect(
    page.getByText(
      "The check is not available right now. Please try again later.",
    ),
  ).toBeVisible();
  await expect(page.getByTestId("finding")).toHaveCount(0);
  await expect(page.getByTestId("no-pattern")).toHaveCount(0);
});

test("network failure: cannot reach Janus, with a retry", async ({ page }) => {
  await withList(page);
  await page.route("**/api/cascades/evaluate", (route) =>
    route.abort("internetdisconnected"),
  );
  await page.goto("/en/results");
  await expect(
    page.getByText("Cannot reach Janus. Check the connection and try again."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("panel errors: evidence and memory unavailable keep the evidence ids and show no numbers", async ({
  page,
}) => {
  await withList(page);
  await stubApi(page, {
    "/cascades/evaluate": { body: fx.evaluation },
    "/evidence/resolve": {
      status: 503,
      body: { error: "integrity_unavailable" },
    },
    "/memory/pair": { status: 503, body: { error: "memory_unavailable" } },
    "/memory/snapshot": { status: 503, body: { error: "memory_unavailable" } },
  });
  await page.goto("/en/results/finding#1");
  await expect(
    page.getByText("Source checks are not available right now."),
  ).toBeVisible();
  await expect(page.getByText("rule:pipc:5")).toBeVisible();
  await expect(
    page.getByText("Collective Memory data is not available right now."),
  ).toBeVisible();
  await expect(page.getByTestId("ci-bar")).toHaveCount(0);
});

test("long German content at 375 px: wraps without horizontal scroll", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "phone", "phone profile only");
  await withList(page);
  await stubApi(page, { "/cascades/evaluate": { body: fx.evaluation } });
  for (const path of ["/de/medicines", "/de/results", "/de/timeline"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expectNoHorizontalScroll(page);
  }
});

test("research: the four Phase 4 entries open their screens, review status, no numbers", async ({
  page,
}) => {
  await page.goto("/en/research");
  // Four Phase 4 entries, the time machine (experience DP58), open data (open-data DP7) and the
  // cascade map (cascade-map DP1), which counts the PIPC patterns ("All 65 …"): a fact of the
  // rule list, not a result.
  await expect(
    page.locator("main").getByRole("link", { name: /^Open/ }),
  ).toHaveCount(7);
  await expect(page.getByTestId("research-review")).toContainText(
    "expert review has not yet been done",
  );
  const text = await page.locator("main").evaluate((m) => {
    const copy = m.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("a[href$='/cascades']").forEach((a) => a.remove());
    return copy.textContent ?? "";
  });
  expect(text).not.toMatch(/\d{2,}/);
});

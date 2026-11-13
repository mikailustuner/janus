// Research tools (research-tools Req 1-4, Phase 1): the data-quality report, the FAERS onset
// table and one row, and "For developers & clinicians". The API is stubbed from synthetic answers
// (src/test/fixtures/research.ts), never from the recorded files; demo mode (bundled recorded
// files) is checked for structure only. C1-C3 in five locales × two
// themes; filters, sorting, the presentation rules of the onset table, downloads, demo mode with
// no request, 503 and 404. Screenshots when RESEARCH_SHOTS_DIR is set.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import type { OnsetRow } from "../src/research/onset";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import {
  comparableMedian,
  dataQualitySet,
  firstRowWith,
  onsetSet,
} from "../src/test/fixtures/research";

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
const dq = dataQualitySet();
const onset = onsetSet();
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../messages/${l}.json`)]),
);
const SHOTS = process.env.RESEARCH_SHOTS_DIR;
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

const rowOut = (p: number) => {
  const t = onset.table;
  return {
    dataset: t.dataset,
    version: t.version,
    faers_receipt_quarters: t.faers_receipt_quarters,
    license: t.license,
    attribution: t.attribution,
    meddra_notice: t.meddra_notice,
    caveats: t.caveats,
    row: t.rows.find((r) => r.pipc_position === p),
  };
};
const firstRow = (status: OnsetRow["status"]) =>
  firstRowWith(onset.table, status);

const stubs = {
  "/open/data-quality": { body: dq.report },
  "/open/faers-onset": { body: onset.table },
  ...Object.fromEntries(
    onset.table.rows.map((r) => [
      `/open/faers-onset/${r.pipc_position}`,
      { body: rowOut(r.pipc_position) },
    ]),
  ),
};

async function checks(page: Page, locale: (typeof LOCALES)[number]) {
  await expect(page.getByTestId("disclaimer")).toHaveText(
    messages[locale].Disclaimer.text,
  );
  await page.waitForLoadState("networkidle");
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  const text = await page.locator("body").innerText();
  expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
  // No TİTCK barcode or GTIN anywhere on a research page.
  expect(text).not.toMatch(/(?<!\d)0?869\d{10}(?!\d)/);
}

async function shot(page: Page, name: string, project: string, theme: string) {
  if (!SHOTS) return;
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({
    path: join(SHOTS, `research-${name}-${project}-${theme}.png`),
    fullPage: true,
  });
}

const PAGES = [
  {
    name: "data-quality",
    path: "/research/data-quality",
    ready: "dq-codes-only",
    text: (m: Record<string, Record<string, string>>) =>
      m.DataQuality!.codesOnly!,
  },
  {
    name: "faers-onset",
    path: "/research/faers-onset",
    ready: "onset-framing",
    text: (m: Record<string, Record<string, string>>) => m.Onset!.framing!,
  },
  {
    name: "faers-onset-row",
    path: `/research/faers-onset/row#${firstRow("described")}`,
    ready: "onset-stats",
    text: null,
  },
  {
    name: "developers",
    path: "/research/developers",
    ready: "dev-not-clinical",
    text: (m: Record<string, Record<string, string>>) =>
      m.Developers!.notClinical!,
  },
] as const;

for (const p of PAGES)
  for (const theme of THEMES)
    for (const locale of locales)
      test(`${p.name}, ${locale}, ${theme}`, async ({ page }, info) => {
        await useTheme(page, theme);
        await stubApi(page, stubs);
        await page.goto(`/${locale}${p.path}`);
        const ready = page.getByRole("main").getByTestId(p.ready);
        if (p.text) await expect(ready).toHaveText(p.text(messages[locale]));
        else await expect(ready).toBeVisible();
        await checks(page, locale);
        if (locale === "en") await shot(page, p.name, info.project.name, theme);
      });

test.describe("data-quality report", () => {
  test("counts, the class filter, show more and the downloads", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto("/en/research/data-quality");
    const total = dq.report.findings.length;
    await expect(page.getByTestId("dq-summary")).toContainText(
      `${total} findings`,
    );
    await expect(page.getByTestId("dq-finding")).toHaveCount(30);
    await page.getByTestId("dq-more").click();
    await expect(page.getByTestId("dq-finding")).toHaveCount(60);
    const confirmed = dq.report.findings.filter(
      (f) => f.class === "confirmed_error",
    ).length;
    await page
      .getByRole("group", { name: "Class" })
      .getByRole("radio", { name: "Confirmed error" })
      .check();
    await expect(page.getByTestId("dq-finding")).toHaveCount(confirmed);
    await expect(
      page.locator(
        '[data-testid="dq-finding"]:not([data-class="confirmed_error"])',
      ),
    ).toHaveCount(0);
    await page.getByTestId("dq-search").fill("zzzz-nothing");
    await expect(
      page.getByText("No finding matches this filter."),
    ).toBeVisible();
    await expect(page.getByTestId("dq-download-csv")).toHaveAttribute(
      "href",
      "/api/open/data-quality.csv",
    );
    await expect(page.getByTestId("dq-download-md")).toHaveAttribute(
      "href",
      "/api/open/data-quality.md",
    );
    await expect(page.getByTestId("dq-upstream")).toContainText(
      "Janus does not send, post or submit any report itself.",
    );
  });

  test("a finding opens with evidence links that leave safely", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto("/en/research/data-quality");
    const first = page.getByTestId("dq-finding").first();
    await first.locator("summary").click();
    const links = first.getByTestId("dq-evidence").locator("a");
    expect(await links.count()).toBeGreaterThan(0);
    for (const a of await links.all()) {
      expect(await a.getAttribute("rel")).toBe("noopener noreferrer");
      expect(await a.getAttribute("href")).toMatch(
        /^https:\/\/(www\.wikidata\.org|atcddd\.fhi\.no)\//,
      );
    }
  });

  test("503: the error and a retry", async ({ page }) => {
    await stubApi(page, {
      "/open/data-quality": {
        status: 503,
        body: { error: "data_quality_unavailable" },
      },
    });
    await page.goto("/en/research/data-quality");
    await expect(
      page.getByRole("alert").filter({ hasText: /\w/ }),
    ).toContainText(messages.en.DataQuality.errors.unavailable);
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  });
});

test.describe("FAERS onset table", () => {
  test("65 rows; sorting by median keeps rows without a median last", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto("/en/research/faers-onset");
    const rows = page.getByTestId("onset-row");
    await expect(rows).toHaveCount(65);
    await page.getByTestId("onset-sort-median").click();
    const th = page.locator("th[aria-sort]");
    await expect(th).toHaveAttribute("aria-sort", "descending");
    const withMedian = onset.table.rows.filter(comparableMedian).length;
    expect(withMedian).toBeGreaterThan(0);
    expect(withMedian).toBeLessThan(onset.table.rows.length);
    const positions = await rows.evaluateAll((els) =>
      els.map((e) => Number(e.querySelector("th")!.textContent)),
    );
    for (const p of positions.slice(withMedian)) {
      const r = onset.table.rows.find((x) => x.pipc_position === p)!;
      expect(comparableMedian(r), `row ${p}`).toBe(false);
    }
    await page.getByTestId("onset-sort-median").click();
    await expect(th).toHaveAttribute("aria-sort", "ascending");
  });

  test("count-only and date-cluster rows never show a median", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    for (const status of ["count_only", "cluster_dominated"] as const) {
      await page.goto(`/en/research/faers-onset/row#${firstRow(status)}`);
      await expect(page.getByTestId("onset-row-status")).toHaveText(
        messages.en.Onset.status[status],
      );
      await expect(page.getByTestId("onset-stats")).toHaveCount(0);
      await expect(page.getByTestId("onset-framing")).toBeVisible();
      await expect(page.getByTestId("onset-caveats")).toBeVisible();
    }
    await page.goto("/en/research/faers-onset");
    for (const s of ["count_only", "cluster_dominated", "no_interval"]) {
      const cells = page.locator(
        `[data-testid="onset-row"][data-status="${s}"] td:nth-of-type(4)`,
      );
      for (const c of await cells.all()) await expect(c).toContainText("—");
    }
  });

  test("a median that only shows same-day heaping is flagged in the table", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto("/en/research/faers-onset");
    const heaping = onset.table.rows.filter(
      (r) => r.median_reflects_zero_heaping,
    );
    expect(heaping.length).toBeGreaterThan(0);
    await expect(page.getByTestId("onset-heaping-flag")).toHaveCount(
      heaping.length,
    );
  });

  test("a small-sample row is labelled as one", async ({ page }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/faers-onset/row#${firstRow("small_sample")}`);
    await expect(page.getByTestId("onset-small-sample")).toBeVisible();
    await expect(page.getByTestId("onset-chart")).toBeVisible();
  });

  test("an unknown or invalid position", async ({ page }) => {
    await stubApi(page, {
      "/open/faers-onset/99": {
        status: 404,
        body: { error: "unknown_position" },
      },
    });
    await page.goto("/en/research/faers-onset/row#99");
    await expect(
      page.getByRole("alert").filter({ hasText: /\w/ }),
    ).toContainText(messages.en.Onset.errors.unknown);
    await page.goto("/en/research/faers-onset/row#abc");
    await expect(
      page.getByText(messages.en.Onset.errors.unknown),
    ).toBeVisible();
  });
});

test("developers: copy a snippet", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await stubApi(page, {});
  await page.goto("/en/research/developers");
  await page.getByRole("main").getByTestId("dev-copy-claude-code").click();
  await expect(page.getByText("Copied.")).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toContain("claude mcp add janus");
  await expect(page.getByRole("main").getByTestId("dev-curl")).toContainText(
    "/api/open/faers-onset/5",
  );
});

// Demo mode reads the bundled recorded files with no request. Their content changes with every
// release, so this checks structure only (the files are checked in src/test/recorded-contract).
test("demo mode: bundled files, downloads from them, no request", async ({
  page,
}) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  const requests = recordRequests(page);
  await page.goto("/en/research/data-quality");
  await expect(page.getByTestId("dq-demo")).toBeVisible();
  await expect(page.getByTestId("dq-finding").first()).toBeVisible();
  const href = await page.getByTestId("dq-download-csv").getAttribute("href");
  expect(href).toMatch(/^data:text\/csv/);
  expect(
    decodeURIComponent(href!.split(",").slice(1).join(",")).length,
  ).toBeGreaterThan(0);
  await page.goto("/en/research/faers-onset");
  await expect(page.getByTestId("onset-demo")).toBeVisible();
  await expect(page.getByTestId("onset-row").first()).toBeVisible();
  await page.goto("/en/research/faers-onset/row#1");
  await expect(page.getByTestId("onset-framing")).toBeVisible();
  expect(requests.filter((r) => r.url().includes("/api/"))).toEqual([]);
});

test("entry points: Research lists the three tools", async ({ page }) => {
  await page.goto("/en/research");
  for (const [name, url] of [
    [messages.en.Research.tools.dataQuality.title, /research\/data-quality$/],
    [messages.en.Research.tools.onset.title, /research\/faers-onset$/],
    [messages.en.Research.tools.developers.title, /research\/developers$/],
  ] as const) {
    await page.goto("/en/research");
    await page
      .getByRole("link", { name: new RegExp(name) })
      .first()
      .click();
    await expect(page).toHaveURL(url);
  }
});

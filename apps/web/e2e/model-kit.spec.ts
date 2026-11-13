// Drug model starter kit (model-kit Req 6; experimental). The API is stubbed from synthetic answers
// (src/test/fixtures/modelkit.ts), never from the recorded release, so a new release cannot break or
// empty these tests; demo mode (bundled recorded file) is checked for structure only. C1-C3 in five locales
// × two themes for the list and three kinds of drug page (validated, not validated with a set,
// without a set); the evidence disclosure by keyboard; the chart and its table; downloads; demo
// mode with no request; 503, 404, an invalid or missing key and the empty list.
// Screenshots when MODELKIT_SHOTS_DIR is set.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import {
  AUDIT,
  KEYS,
  modelKitSet,
  type ModelKitSet,
} from "../src/test/fixtures/modelkit";

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

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const read = (p: string) =>
  JSON.parse(readFileSync(join(import.meta.dirname, p), "utf8"));
const kit = modelKitSet();
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../messages/${l}.json`)]),
);
const SHOTS = process.env.MODELKIT_SHOTS_DIR;
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

/** The list route as the API answers it: name search, status, has_set, limit and offset. */
const listStub =
  (r: ModelKitSet) =>
  (_body: unknown, url: URL): { body: unknown } => {
    const all = r.drugs.drugs as Json[];
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    const st = url.searchParams.get("status");
    const hasSet = url.searchParams.get("has_set") === "true";
    const limit = Number(url.searchParams.get("limit") ?? 50);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const kept = all.filter(
      (d) =>
        (!q ||
          d.key.includes(q.replaceAll(" ", "_")) ||
          d.name.toLowerCase().includes(q)) &&
        (!st || d.status === st) &&
        (!hasSet || d.has_set),
    );
    const counts: Record<string, number> = {
      all: all.length,
      with_set: all.filter((d) => d.has_set).length,
    };
    for (const s of ["validated", "not_validated", "failed"])
      counts[s] = all.filter((d) => d.status === s).length;
    return {
      body: {
        ...r.drugs,
        drugs: kept.slice(offset, offset + limit),
        total: kept.length,
        offset,
        limit,
        counts,
      },
    };
  };
const stubsOf = (r: ModelKitSet) => ({
  "/modelkit/drugs": listStub(r),
  "/modelkit/validation": { body: r.validation },
  ...Object.fromEntries(
    Object.keys(r.drug).flatMap((k) => [
      [`/modelkit/drugs/${k}`, { body: r.drug[k] }],
      [`/modelkit/drugs/${k}/evidence`, { body: r.evidence[k] }],
    ]),
  ),
});
const stubs = stubsOf(kit);

const PAGE = 25; // drugs per page of the list
const VALIDATED = KEYS.validated;
const FAILED = KEYS.failed; // one Cmax point outside 2-fold (strict rule, owner decision 2026-11-11)
const WITH_SET = KEYS.notValidated;
const NO_SET = KEYS.noSet;
const HALF_LIFE = KEYS.validated;
const REL_DRUG = KEYS.longEvidence; // set, validation points, 24 excluded evidence rows

/**
 * No table cell wraps inside a word and no scroll region pokes out of the viewport: every cell of
 * every table is at least as wide as its longest word (canvas measurement in the cell's own font),
 * and each scroller ends inside the viewport (a regression check for the 375 px layout).
 */
async function expectTablesFit(page: Page): Promise<void> {
  const bad = await page.evaluate(() => {
    const canvas = document.createElement("canvas").getContext("2d")!;
    const out: string[] = [];
    for (const cell of document.querySelectorAll<HTMLTableCellElement>(
      "main table th, main table td",
    )) {
      const r = cell.getBoundingClientRect();
      if (r.width === 0) continue;
      const cs = getComputedStyle(cell);
      canvas.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const words = (cell.innerText || "")
        .split(/[\s\-\u2013\u2014]+/)
        .filter(Boolean);
      const longest = Math.max(
        0,
        ...words.map((w) => canvas.measureText(w).width),
      );
      const inner =
        r.width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      if (cell.colSpan > 1) continue; // the evidence panel wraps long ids by design
      if (inner + 1 < longest)
        out.push(
          `${cell.tagName} "${(cell.innerText || "").slice(0, 30)}" ${inner.toFixed(0)} < ${longest.toFixed(0)}`,
        );
    }
    for (const sc of document.querySelectorAll<HTMLElement>(
      "[data-testid=mk-scroll]",
    )) {
      const r = sc.getBoundingClientRect();
      if (r.right > window.innerWidth + 0.5 || r.left < -0.5)
        out.push(`scroller outside viewport ${r.left}..${r.right}`);
    }
    return out;
  });
  expect(bad, "cells narrower than their longest word").toEqual([]);
}

async function checks(page: Page, locale: (typeof LOCALES)[number]) {
  const m = messages[locale].ModelKit;
  await expect(page.getByTestId("disclaimer")).toHaveText(
    messages[locale].Disclaimer.text,
  );
  await page.waitForLoadState("networkidle");
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
  // The two statements and the Experimental badge are visible (Req 6).
  await expect(page.getByTestId("mk-research-use")).toHaveText(m.researchUse);
  await expect(page.getByTestId("mk-review")).toHaveText(m.expertReview);
  await expect(page.getByTestId("mk-experimental").first()).toHaveText(
    m.experimental,
  );
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await expectTablesFit(page);
  await expectTouchTargets(page);
  const text = await page.locator("body").innerText();
  expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
  if (locale === "en") {
    expect(text).not.toMatch(
      /\b(safe|safely|safety|recommended dose|AI)\b|artificial intelligence/i,
    );
    expect(text).not.toMatch(/reviewed by|peer.reviewed|approved by/i);
  }
}

async function shot(page: Page, name: string, project: string, theme: string) {
  if (!SHOTS) return;
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({
    path: join(SHOTS, `modelkit-${name}-${project}-${theme}.png`),
    fullPage: true,
  });
}

const PAGES = [
  { name: "list", path: "/research/model-kit", open: null },
  { name: "report", path: "/research/model-kit/report", open: null },
  {
    name: "drug-long-evidence",
    path: `/research/model-kit/drug#${REL_DRUG}`,
    open: "cl",
  },
  {
    name: "drug-validated",
    path: `/research/model-kit/drug#${VALIDATED}`,
    open: "cl",
  },
  {
    name: "drug-failed",
    path: `/research/model-kit/drug#${FAILED}`,
    open: "cl",
  },
  { name: "drug-not-validated", path: `/research/model-kit/drug#${WITH_SET}` },
  { name: "drug-no-set", path: `/research/model-kit/drug#${NO_SET}` },
] as const;

for (const p of PAGES)
  for (const theme of THEMES)
    for (const locale of locales)
      test(`${p.name}, ${locale}, ${theme}`, async ({ page }, info) => {
        await useTheme(page, theme);
        await stubApi(page, stubs);
        await page.goto(`/${locale}${p.path}`);
        await expect(page.getByTestId("mk-research-use")).toBeVisible();
        if (p.name.startsWith("list"))
          await expect(page.getByTestId("mk-report-link")).toBeVisible();
        else if (p.name.startsWith("report"))
          await expect(page.getByTestId("mk-report")).toBeVisible();
        else await expect(page.getByTestId("mk-validation")).toBeVisible();
        if ("open" in p && p.open) {
          await page.getByTestId(`mk-value-${p.open}`).click();
          await expect(page.getByTestId("mk-quote").first()).toBeVisible();
        }
        await checks(page, locale);
        if (locale === "en" || locale === "tr")
          await shot(page, `${p.name}-${locale}`, info.project.name, theme);
      });

test.describe("list", () => {
  test("every drug has the Experimental badge, a status, a reason and n", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto("/en/research/model-kit");
    const all = kit.drugs.drugs as Json[];
    const rows = page.getByTestId("mk-drug");
    await expect(rows).toHaveCount(Math.min(PAGE, all.length));
    for (const row of await rows.all()) {
      await expect(row.getByTestId("mk-experimental")).toHaveText(
        "Experimental",
      );
      await expect(row.getByTestId("mk-status")).toBeVisible();
      await expect(row).toContainText(/\d+ stud/);
    }
    await expect(page.getByTestId("mk-summary")).toContainText(
      `${all.length} drug`,
    );
    // the system report has its own page, linked from the list
    await expect(page.getByTestId("mk-report-link")).toBeVisible();
  });

  test("search, status filter and pages narrow the list and open a drug", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto("/en/research/model-kit");
    const all = kit.drugs.drugs as Json[];
    const status = "failed";
    const failed = all.find((d) => d.key === FAILED);
    expect(failed).toBeTruthy();
    // status filter
    await page.getByTestId("mk-status-filter").selectOption(status);
    const nFailed = all.filter((d) => d.status === status).length;
    await expect(page.getByTestId("mk-matches")).toContainText(
      `${nFailed} drug`,
    );
    await expect(page.getByTestId("mk-drug").first()).toContainText(
      messages.en.ModelKit.status.failed,
    );
    await page.getByTestId("mk-status-filter").selectOption("");
    // name search (waits for a pause in typing) and a search without a match
    await page.getByTestId("mk-search").fill(failed!.name.slice(0, 5));
    await expect(
      page.locator('[data-testid="mk-drug"]').filter({ hasText: failed!.name }),
    ).toBeVisible();
    await page.getByTestId("mk-search").fill("zzzzzzzz");
    await expect(page.getByTestId("mk-matches")).toContainText("0 drugs");
    await expect(
      page.getByText(messages.en.ModelKit.list.noMatch),
    ).toBeVisible();
    await page.getByTestId("mk-search").fill("");
    // pages: 25 at a time, previous disabled on the first page
    expect(all.length).toBeGreaterThan(PAGE);
    await expect(page.getByTestId("mk-prev")).toBeDisabled();
    await page.getByTestId("mk-next").click();
    await expect(page.getByTestId("mk-range")).toContainText(
      `${PAGE + 1}–${Math.min(2 * PAGE, all.length)} of ${all.length}`,
    );
    await expect(page.getByTestId("mk-drug").first()).toContainText(
      all[PAGE]!.name,
    );
    await page.getByTestId("mk-prev").click();
    await expect(page.getByTestId("mk-range")).toContainText(`1–${PAGE}`);
    // a row opens its drug page
    await page.getByTestId("mk-search").fill(failed!.name);
    await page
      .getByRole("link", { name: new RegExp(failed!.name) })
      .first()
      .click();
    await expect(page).toHaveURL(new RegExp(`model-kit/drug#${failed!.key}$`));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      failed!.name,
    );
  });

  test("empty and 503", async ({ page }) => {
    await stubApi(page, {
      "/modelkit/drugs": {
        body: {
          ...kit.drugs,
          drugs: [],
          total: 0,
          counts: {
            all: 0,
            with_set: 0,
            validated: 0,
            not_validated: 0,
            failed: 0,
          },
        },
      },
    });
    await page.goto("/en/research/model-kit");
    await expect(page.getByText(messages.en.ModelKit.list.empty)).toBeVisible();
    const p2 = await page.context().newPage();
    await stubApi(p2, {
      "/modelkit/drugs": {
        status: 503,
        body: { error: "modelkit_unavailable" },
      },
    });
    await p2.goto("/en/research/model-kit");
    await expect(p2.getByRole("alert").filter({ hasText: /\w/ })).toContainText(
      messages.en.ModelKit.errors.unavailable,
    );
    await expect(p2.getByRole("button", { name: "Try again" })).toBeVisible();
  });
});

test.describe("drug page", () => {
  for (const theme of THEMES)
    for (const locale of ["en", "pt"] as const)
      test(`leave one study out: rebuilt points are counted, ${locale}, ${theme}`, async ({
        page,
      }, info) => {
        // a drug whose points are marked as predicted by a set built without their study (DP-M40)
        const d = kit.drug[REL_DRUG]!;
        const pts = d.validation.points as Json[];
        const body = {
          ...d,
          validation: {
            ...d.validation,
            points: pts.map((p) => ({ ...p, rebuilt_without_study: true })),
          },
        };
        await useTheme(page, theme);
        await stubApi(page, {
          ...stubs,
          [`/modelkit/drugs/${REL_DRUG}`]: { body },
        });
        await page.goto(`/${locale}/research/model-kit/drug#${REL_DRUG}`);
        await expect(page.getByTestId("mk-validation")).toBeVisible();
        await expect(page.getByTestId("mk-rebuilt")).toContainText(
          String(pts.length),
        );
        await expectNoHorizontalScroll(page);
        await expectNoAxeViolations(page);
        await shot(page, `rebuilt-${locale}`, info.project.name, theme);
        if (SHOTS)
          await page.getByTestId("mk-validation").screenshot({
            path: join(
              SHOTS,
              `modelkit-rebuilt-section-${locale}-${info.project.name}-${theme}.png`,
            ),
          });
      });

  test("a long evidence table shows 20 rows first and all on request", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    const excluded = kit.evidence[REL_DRUG]!.rows.filter(
      (r: Json) => r.role === "excluded",
    );
    expect(excluded.length).toBeGreaterThan(20);
    await page.goto(`/en/research/model-kit/drug#${REL_DRUG}`);
    const rows = page.getByTestId("mk-excluded").getByTestId("mk-ev-row");
    await expect(rows).toHaveCount(20);
    const more = page.getByTestId("mk-excluded-more");
    await expect(more).toHaveAttribute("aria-expanded", "false");
    await more.click();
    await expect(rows).toHaveCount(excluded.length);
    await expect(more).toHaveAttribute("aria-expanded", "true");
  });

  test("a value opens its evidence by keyboard: quote, source, both readers", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${VALIDATED}`);
    const set = kit.drug[VALIDATED]!.parameter_set!;
    const cl = set.params.find((p) => p.name === "cl")!;
    const row = kit.evidence[VALIDATED]!.rows.find(
      (r) => r.id === cl.evidence_ids[0],
    )!;
    const btn = page.getByTestId("mk-value-cl");
    await expect(btn).toHaveAttribute("aria-expanded", "false");
    await btn.focus();
    await page.keyboard.press("Enter");
    await expect(btn).toHaveAttribute("aria-expanded", "true");
    const pop = page.getByTestId("mk-popover");
    await expect(pop.getByTestId("mk-quote").first()).toHaveText(row.quote);
    await expect(pop.getByTestId("mk-quote").first()).toHaveAttribute(
      "lang",
      "en",
    );
    await expect(pop.getByTestId("mk-locator").first()).toHaveText(
      row.source_locator,
    );
    await expect(pop.getByTestId("mk-reader-a").first()).toContainText(
      "Reader A",
    );
    await expect(pop.getByTestId("mk-reader-b").first()).toContainText(
      "Reader B",
    );
    await expect(pop.getByTestId("mk-confirm").first()).toContainText(
      row.confirm_reason,
    );
    const link = pop.getByTestId("mk-source-link").first();
    await expect(link).toHaveAttribute("href", row.source_url!);
    await expect(link).toHaveAttribute("rel", "noopener noreferrer");
    await expect(link).toHaveAttribute("target", "_blank");
    await page.keyboard.press("Space");
    await expect(btn).toHaveAttribute("aria-expanded", "false");
    await expect(pop).toHaveCount(0);
  });

  test("apparent parameters are labelled; a half-life warning shows both numbers", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${FAILED}`);
    await expect(page.getByTestId("mk-apparent")).toContainText("CL/F, V/F");
    await expect(page.getByTestId("mk-param-table")).toContainText(
      "CL/F (apparent)",
    );
    await page.goto(`/en/research/model-kit/drug#${HALF_LIFE}`);
    const w = kit.drug[HALF_LIFE]!.parameter_set!;
    const fmt = (x: number) => (Math.round(x * 10) / 10).toString();
    const box = page.getByTestId("mk-warnings");
    await expect(box).toContainText(fmt(w.implied_half_life_h!));
    await expect(box).toContainText(fmt(w.stated_half_life_h!));
    await expect(box).toContainText("half-life");
    await expect(page.getByTestId("mk-legend")).toContainText("A");
  });

  test("strict rule: a point outside 2-fold fails the drug and is named with its suspect parameter", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${FAILED}`);
    await expect(page.getByTestId("mk-status").first()).toHaveAttribute(
      "data-status",
      "failed",
    );
    const bad = kit.drug[FAILED]!.validation.points.filter(
      (p: Json) => !p.within_2_fold,
    );
    expect(bad.length).toBeGreaterThan(0);
    await expect(
      page.getByTestId("mk-failed-points").locator("li"),
    ).toHaveCount(bad.length);
    await expect(page.getByTestId("mk-suspect")).toBeVisible();
    await expect(page.getByTestId("mk-status-reasons")).toContainText(
      "outside 2-fold",
    );
  });

  test("the chart has a name, a band and a table with every point", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${VALIDATED}`);
    const pts = kit.drug[VALIDATED]!.validation.points.length;
    const chart = page.getByTestId("mk-chart");
    await expect(chart.getByRole("img").first()).toHaveAttribute(
      "aria-label",
      /Log-log scatter of \d+ held-out observations/,
    );
    await expect(chart.locator("polygon")).toHaveCount(1);
    await expect(chart.locator("circle, svg > rect")).not.toHaveCount(0);
    await expect(
      page.getByTestId("mk-chart-table").locator("tbody tr"),
    ).toHaveCount(pts);
    await expect(page.getByTestId("mk-metrics")).toContainText("AUC");
    await expect(page.getByTestId("mk-metrics")).toContainText("Cmax");
    await expect(page.getByTestId("mk-interval-auc")).toContainText(
      "no interval is shown",
    );
    await expect(page.getByTestId("mk-interval-cmax")).toContainText(
      "No interval is shown",
    );
    await expect(page.getByTestId("mk-status-explain")).toBeVisible();
  });

  test("a drug without a set: reasons, evidence, no chart, no downloads", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${NO_SET}`);
    await expect(page.getByTestId("mk-noset-reasons")).toContainText(
      "No confirmed clearance",
    );
    await expect(page.getByTestId("mk-no-points")).toBeVisible();
    await expect(page.getByTestId("mk-chart")).toHaveCount(0);
    await expect(page.getByTestId("mk-downloads")).toHaveCount(0);
    await expect(page.getByTestId("mk-params")).toHaveCount(0);
    await expect(page.getByTestId("mk-ev-row")).not.toHaveCount(0);
    await page.getByTestId("mk-ev-value").first().click();
    await expect(page.getByTestId("mk-quote").first()).toBeVisible();
  });

  test("live downloads link to the zip routes", async ({ page }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${VALIDATED}`);
    for (const t of kit.drug[VALIDATED]!.targets)
      await expect(page.getByTestId(`mk-download-${t}`)).toHaveAttribute(
        "href",
        `/api/modelkit/drugs/${VALIDATED}/export/${t}`,
      );
  });

  test("503, an unknown drug, an invalid key and no key", async ({ page }) => {
    await stubApi(page, {
      [`/modelkit/drugs/${VALIDATED}`]: {
        status: 503,
        body: { error: "modelkit_unavailable" },
      },
      "/modelkit/drugs/nothere": {
        status: 404,
        body: { error: "unknown_drug" },
      },
      [`/modelkit/drugs/${VALIDATED}/evidence`]: {
        body: kit.evidence[VALIDATED]!,
      },
      "/modelkit/drugs/nothere/evidence": {
        status: 404,
        body: { error: "unknown_drug" },
      },
    });
    const alert = page.getByRole("alert").filter({ hasText: /\w/ });
    await page.goto(`/en/research/model-kit/drug#${VALIDATED}`);
    await expect(alert).toContainText(messages.en.ModelKit.errors.unavailable);
    await page.goto("/en/research/model-kit/drug#nothere");
    await page.reload();
    await expect(alert).toContainText(messages.en.ModelKit.errors.unknown);
    const seen = recordRequests(page);
    for (const hash of ["#Bad-Key", "#../x", ""]) {
      await page.goto(`/en/research/model-kit/drug${hash}`);
      await page.reload();
      await expect(
        page.getByText(messages.en.ModelKit.errors.invalidKey),
      ).toBeVisible();
    }
    expect(
      seen.filter((r) => new URL(r.url()).pathname.startsWith("/api/")),
    ).toEqual([]);
  });
});

test.describe("system report", () => {
  test("counts, the gate, intervals, precision and what is missing", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto("/en/research/model-kit/report");
    await expect(page.getByTestId("mk-report")).toBeVisible();
    await expect(page.getByTestId("mk-gate")).toContainText(
      String(kit.validation.n_drugs_both_tested),
    );
    await expect(page.getByTestId("mk-rows")).toContainText(
      String(kit.validation.rows_total),
    );
    await expect(page.getByTestId("mk-formulation-table")).toContainText(
      "Not stated",
    );
    for (const i of kit.validation.intervals as Json[])
      await expect(page.getByTestId(`mk-interval-${i.metric}`)).toContainText(
        i.shown ? "shown" : "independent held-out studies",
      );
    await expect(page.getByTestId("mk-missing")).toContainText(
      "Expert review has not yet been done",
    );
    if (kit.validation.precision)
      await expect(page.getByTestId("mk-precision")).toContainText(
        `n = ${kit.validation.precision.n}`,
      );
    await expect(page.getByTestId("mk-precision")).toBeVisible();
    // milestone M5: the two document sources with their measured precision, and the study identity rule
    const docs = page.getByTestId("mk-doc-source");
    await expect(docs).toHaveCount(kit.validation.document_sources.length);
    for (const [i, d] of (kit.validation.document_sources as Json[]).entries())
      await expect(docs.nth(i)).toContainText(
        d.published ? "Published in this release" : "Held back",
      );
    await expect(page.getByTestId("mk-identity")).toContainText(
      `of ${kit.validation.study_identity.test_studies_without_rule} held-out studies`,
    );
  });

  test("503 and the back link", async ({ page }) => {
    await stubApi(page, {
      "/modelkit/validation": {
        status: 503,
        body: { error: "modelkit_unavailable" },
      },
    });
    await page.goto("/en/research/model-kit/report");
    await expect(
      page.getByRole("link", { name: /Back to the drugs/ }),
    ).toBeVisible();
    await expect(page.getByTestId("mk-research-use")).toBeVisible();
  });
});

// Demo mode reads the bundled recorded file with no request. The content changes with every
// release, so this checks structure only: the list and the report render, search and the "has a
// set" filter work in the browser, a row opens a drug page, nothing is requested. Download buttons
// being off in the demo is covered by the unit test of demoModelKit (`downloads` is false).
test.describe("demo mode", () => {
  test("answers from the bundled file with no request", async ({ page }) => {
    await page.addInitScript(() =>
      sessionStorage.setItem("janus.v1.demo", "istanbul"),
    );
    const seen = recordRequests(page);
    await page.goto("/en/research/model-kit");
    const rows = page.getByTestId("mk-drug");
    await expect(rows.first()).toBeVisible();
    const name = (
      await rows.first().locator("span").first().innerText()
    ).trim();
    expect(name).not.toBe("");
    await expect(page.getByTestId("mk-demo")).toBeVisible();
    // the demo searches the bundled list in the browser, still with no request
    await page.getByTestId("mk-search").fill(name.slice(0, 5));
    await expect(rows.first()).toBeVisible();
    await page.getByTestId("mk-search").fill("");
    await expect(page.getByTestId("mk-report-link")).toBeVisible();
    // a row opens its drug page (the bundled file holds only some drug pages, so the page is
    // checked for rendering, not for a set)
    await page.getByTestId("mk-has-set").check();
    await expect(rows.first()).toBeVisible();
    await rows.first().click();
    await expect(page).toHaveURL(/model-kit\/drug#[a-z]/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
    await page.goto("/en/research/model-kit/report");
    await expect(page.getByTestId("mk-report")).toBeVisible();
    await page.goto("/en/research/model-kit/drug#nothere");
    await page.reload();
    await expect(
      page.getByText(messages.en.ModelKit.errors.unknown),
    ).toBeVisible();
    expect(
      seen
        .filter((r) => new URL(r.url()).pathname.startsWith("/api/"))
        .map((r) => r.url()),
    ).toEqual([]);
  });
});

// Special populations (milestone M4): exposure ratios of older adults and of renal and hepatic impairment as
// quoted from US labels, atlas rows as unconfirmed evidence, and the system report's counts.
const SP_DRUG = KEYS.fewStatements;
const SP_MANY = KEYS.manyStatements; // eight statements
const SP_ATLAS = KEYS.manyStatements;
const SP_NONE = KEYS.validated;

test.describe("special populations", () => {
  test("statements are quoted evidence with the label version and a link", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${SP_DRUG}`);
    const sec = page.getByTestId("mk-sp");
    await expect(sec).toBeVisible();
    await expect(sec).toContainText(messages.en.ModelKit.sp.intro);
    await expect(page.getByTestId("mk-sp-notes")).toContainText(
      messages.en.ModelKit.reasons.sp_statements_note,
    );
    const statements = kit.drug[SP_DRUG]!.special_populations
      .statements as Json[];
    const shown = page.getByTestId("mk-sp-statement");
    await expect(shown).toHaveCount(Math.min(6, statements.length));
    const first = shown.first();
    await expect(first.locator("blockquote")).toHaveAttribute("lang", "en");
    await expect(first.locator("blockquote")).toContainText(
      statements[0]!.quote.slice(0, 40),
    );
    const link = first.getByRole("link", {
      name: messages.en.ModelKit.sp.openLabel,
    });
    await expect(link).toHaveAttribute(
      "href",
      new RegExp(
        `^https://dailymed\\.nlm\\.nih\\.gov/.*setid=${statements[0]!.set_id}$`,
      ),
    );
    await expect(first).toContainText(`version ${statements[0]!.version}`);
    // no dose advice, no verdict wording
    const text = (await sec.innerText()).toLowerCase();
    expect(text).not.toMatch(/\b(safe|recommended dose|should take)\b/);
    await expectNoAxeViolations(page);
    await expectNoHorizontalScroll(page);
  });

  test("a long list shows six statements first and all on request", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${SP_MANY}`);
    const n = (kit.drug[SP_MANY]!.special_populations.statements as Json[])
      .length;
    await expect(page.getByTestId("mk-sp-statement")).toHaveCount(6);
    await page.getByTestId("mk-sp-more").click();
    await expect(page.getByTestId("mk-sp-statement")).toHaveCount(n);
    await expectNoHorizontalScroll(page);
  });

  test("atlas rows are collapsed, quoted and marked unconfirmed", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${SP_ATLAS}`);
    const box = page.getByTestId("mk-sp-atlas");
    await expect(box).toBeVisible();
    await expect(box.getByTestId("mk-sp-atlas-row").first()).toBeHidden();
    await box.locator("summary").click();
    const row = box.getByTestId("mk-sp-atlas-row").first();
    await expect(row).toBeVisible();
    await expect(row).toContainText(
      messages.en.ModelKit.reasons.automated_extraction_unconfirmed,
    );
    await expect(row.locator("blockquote")).toHaveAttribute("lang", "en");
    await expectNoAxeViolations(page);
  });

  test("a drug without a confirmed statement says so", async ({ page }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${SP_NONE}`);
    await expect(page.getByTestId("mk-sp")).toContainText(
      messages.en.ModelKit.sp.empty,
    );
    await expect(page.getByTestId("mk-sp-statement")).toHaveCount(0);
  });

  test("the system report counts the statements and shows the precision", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto("/en/research/model-kit/report");
    const sp = page.getByTestId("mk-sp-system");
    await expect(sp).toBeVisible();
    const s = kit.validation.special_populations as Json;
    await expect(sp).toContainText(String(s.statements));
    await expect(sp).toContainText(String(s.precision!.n));
    await expect(sp).toContainText(messages.en.ModelKit.sp.systemIntro);
  });
});

// Milestone M6: with an expert audit record in the answers the review line gives precision, n and
// date (plan 6.4); without one it stays "Expert review has not yet been done." (the checks above).
const auditStubs = stubsOf(modelKitSet(AUDIT));

for (const theme of THEMES)
  for (const locale of ["en", "tr"] as const)
    for (const path of [
      "/research/model-kit",
      "/research/model-kit/report",
      `/research/model-kit/drug#${FAILED}`,
    ])
      test(`expert audit line, ${path}, ${locale}, ${theme}`, async ({
        page,
      }, info) => {
        await useTheme(page, theme);
        await stubApi(page, auditStubs);
        await page.goto(`/${locale}${path}`);
        await page.waitForLoadState("networkidle");
        const review = page.getByTestId("mk-review");
        await expect(review).toHaveAttribute("data-audit", "yes");
        await expect(review).toHaveText(
          locale === "en"
            ? "Expert audit: precision 0.97 (n = 320, 2027\u201101\u201115)."
            : "Uzman denetimi: doğruluk 0,97 (n = 320, 2027\u201101\u201115).",
        );
        await expect(review).not.toHaveText(
          messages[locale].ModelKit.expertReview,
        );
        await expectNoAxeViolations(page);
        await expectNoHorizontalScroll(page);
        if (path === "/research/model-kit")
          await shot(page, `audit-${locale}`, info.project.name, theme);
      });

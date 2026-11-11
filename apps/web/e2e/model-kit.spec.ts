// Drug model starter kit (model-kit Req 6; experimental). The API is stubbed from the answers
// recorded from the real local API (src/modelkit/modelkit.recorded.json). C1-C3 in five locales
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
const fx = read("../src/modelkit/modelkit.recorded.json") as {
  drugs: Json;
  validation: Json;
  drug: Record<string, Json>;
  evidence: Record<string, Json>;
};
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../messages/${l}.json`)]),
);
const SHOTS = process.env.MODELKIT_SHOTS_DIR;
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

const stubs = {
  "/modelkit/drugs": { body: fx.drugs },
  "/modelkit/validation": { body: fx.validation },
  ...Object.fromEntries(
    Object.keys(fx.drug).flatMap((k) => [
      [`/modelkit/drugs/${k}`, { body: fx.drug[k] }],
      [`/modelkit/drugs/${k}/evidence`, { body: fx.evidence[k] }],
    ]),
  ),
};

const VALIDATED = "sunitinib";
const WITH_SET = "dolutegravir";
const NO_SET = "gabapentin";
const HALF_LIFE = "ertugliflozin";

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
  {
    name: "drug-validated",
    path: `/research/model-kit/drug#${VALIDATED}`,
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
        if (p.name === "list")
          await expect(page.getByTestId("mk-system")).toBeVisible();
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
    const rows = page.getByTestId("mk-drug");
    await expect(rows).toHaveCount(fx.drugs.drugs.length);
    for (const row of await rows.all()) {
      await expect(row.getByTestId("mk-experimental")).toHaveText(
        "Experimental",
      );
      await expect(row.getByTestId("mk-status")).toBeVisible();
      await expect(row).toContainText(/\d+ stud/);
    }
    const sunitinib = fx.drugs.drugs.find((d: Json) => d.key === VALIDATED);
    await expect(
      page.locator(`[data-testid="mk-drug"]`).filter({ hasText: "Sunitinib" }),
    ).toContainText(sunitinib.status === "validated" ? "Validated" : "Not");
    await expect(page.getByTestId("mk-interval")).toContainText(
      "No interval is shown",
    );
    await page.getByRole("link", { name: /Sunitinib/ }).click();
    await expect(page).toHaveURL(/model-kit\/drug#sunitinib$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Sunitinib",
    );
  });

  test("empty and 503", async ({ page }) => {
    await stubApi(page, {
      "/modelkit/drugs": { body: { ...fx.drugs, drugs: [] } },
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
  test("a value opens its evidence by keyboard: quote, source, both readers", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${VALIDATED}`);
    const set = fx.drug[VALIDATED]!.parameter_set;
    const cl = set.params.find((p: Json) => p.name === "cl");
    const row = fx.evidence[VALIDATED]!.rows.find(
      (r: Json) => r.id === cl.evidence_ids[0],
    );
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
    await expect(link).toHaveAttribute("href", row.source_url);
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
    await page.goto(`/en/research/model-kit/drug#${VALIDATED}`);
    await expect(page.getByTestId("mk-apparent")).toContainText("CL/F, V/F");
    await expect(page.getByTestId("mk-param-table")).toContainText(
      "CL/F (apparent)",
    );
    await page.goto(`/en/research/model-kit/drug#${HALF_LIFE}`);
    const w = fx.drug[HALF_LIFE]!.parameter_set;
    const fmt = (x: number) => (Math.round(x * 10) / 10).toString();
    const box = page.getByTestId("mk-warnings");
    await expect(box).toContainText(fmt(w.implied_half_life_h));
    await expect(box).toContainText(fmt(w.stated_half_life_h));
    await expect(box).toContainText("half-life");
    await expect(page.getByTestId("mk-legend")).toContainText("A");
  });

  test("the chart has a name, a band and a table with every point", async ({
    page,
  }) => {
    await stubApi(page, stubs);
    await page.goto(`/en/research/model-kit/drug#${VALIDATED}`);
    const pts = fx.drug[VALIDATED]!.validation.points.length;
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
    await expect(page.getByTestId("mk-interval")).toContainText(
      "No interval is shown",
    );
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
    for (const t of fx.drug[VALIDATED]!.targets)
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
        body: fx.evidence[VALIDATED]!,
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

test.describe("demo mode", () => {
  test("answers from the recorded file with no request; downloads are off", async ({
    page,
  }) => {
    await page.addInitScript(() =>
      sessionStorage.setItem("janus.v1.demo", "istanbul"),
    );
    const seen = recordRequests(page);
    await page.goto("/en/research/model-kit");
    await expect(page.getByTestId("mk-drug")).toHaveCount(
      fx.drugs.drugs.length,
    );
    await expect(page.getByTestId("mk-system")).toBeVisible();
    await expect(page.getByTestId("mk-demo")).toBeVisible();
    await page.goto(`/en/research/model-kit/drug#${VALIDATED}`);
    await expect(page.getByTestId("mk-validation")).toBeVisible();
    await page.getByTestId("mk-value-cl").click();
    await expect(page.getByTestId("mk-quote").first()).toBeVisible();
    for (const t of fx.drug[VALIDATED]!.targets)
      await expect(page.getByTestId(`mk-download-${t}`)).toBeDisabled();
    await expect(page.getByTestId("mk-dl-demo")).toContainText(
      "Downloads need the live service",
    );
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

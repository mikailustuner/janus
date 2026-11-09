// Time machine screens (experience Req 30, DP58–DP64; time-machine design §10): the API stubbed
// from answers recorded from the real local API (src/timemachine/fixture.recorded.json). C1–C3 in
// five locales × two themes on the index, a substance and two cascades; rendering rules (no PBPK
// for a compartmental model, "reports", no shape for a small sample, validation verdicts with the
// failures, review label, in-silico line); chart tables; demo mode with no request; the patient
// sentence in the finding detail and its absence elsewhere; links from the séance and the map.
// Screenshots at 375 and 1280 in both themes when TM_SHOTS_DIR is set.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { themeWords } from "../src/i18n/reassurance";

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
const fx = read("../src/timemachine/fixture.recorded.json") as {
  catalogue: { substance_ids: string[]; cascade_ids: string[] };
  substances: Record<string, unknown>;
  cascades: Record<string, unknown>;
};
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../messages/${l}.json`)]),
);
const SHOTS = process.env.TM_SHOTS_DIR;
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

function stubs() {
  const s: Record<string, { status?: number; body: unknown }> = {
    "/timemachine/catalogue": { body: fx.catalogue },
  };
  for (const [id, b] of Object.entries(fx.substances))
    s[`/timemachine/substance/${id}`] = { body: b };
  for (const [id, b] of Object.entries(fx.cascades))
    s[`/timemachine/cascade/${id}`] = { body: b };
  return s;
}

async function checks(
  page: Page,
  locale: (typeof LOCALES)[number],
  glass: boolean,
) {
  await page.waitForLoadState("networkidle");
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  const text = await page.locator("body").innerText();
  expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
  if (glass) expect(findForbiddenPhrases(text, themeWords[locale])).toEqual([]);
  const m = messages[locale];
  await expect(page.getByTestId("disclaimer")).toHaveText(m.Disclaimer.text);
  await expect(page.getByTestId("tm-review")).toHaveText(m.TimeMachine.review);
  await expect(page.getByTestId("tm-in-silico")).toHaveText(
    m.TimeMachine.inSilico,
  );
}

const PAGES = [
  { name: "index", path: "/research/time-machine", ready: "tm-substances" },
  {
    name: "rhubarb",
    path: "/research/time-machine/substance#rhubarb",
    ready: "tm-exposure-card",
  },
  {
    name: "amlodipine",
    path: "/research/time-machine/cascade#amlodipine_oedema_diuretic",
    ready: "tm-curve",
  },
  {
    name: "antipsychotic",
    path: "/research/time-machine/cascade#antipsychotic_eps_antiparkinson",
    ready: "tm-css",
  },
];

for (const theme of THEMES)
  for (const locale of locales)
    test(`time machine, ${locale}, ${theme}`, async ({ page }, info) => {
      await useTheme(page, theme);
      await stubApi(page, stubs());
      for (const p of PAGES) {
        await page.goto(`/${locale}${p.path}`);
        await expect(page.getByTestId(p.ready).first()).toBeVisible();
        await checks(page, locale, theme === "glass");
        if (SHOTS && locale === "en") {
          mkdirSync(SHOTS, { recursive: true });
          await page.screenshot({
            path: join(SHOTS, `tm-${p.name}-${info.project.name}-${theme}.png`),
            fullPage: true,
          });
        }
      }
    });

test("rendering rules: compartmental without PBPK, reports, verdicts with failures, chart tables", async ({
  page,
}) => {
  await stubApi(page, stubs());
  const m = messages.en.TimeMachine;
  // Amlodipine: compartmental, 35 reports, not a small sample, agrees.
  await page.goto(
    "/en/research/time-machine/cascade#amlodipine_oedema_diuretic",
  );
  await expect(page.getByTestId("tm-curve")).toBeVisible();
  await expect(page.locator("main")).not.toContainText(/PBPK/);
  await expect(page.getByTestId("tm-onset-sentence")).toContainText(
    "35 reports",
  );
  await expect(page.locator("main")).not.toContainText(/\bpeople\b(?! *\.)/i);
  await expect(page.getByTestId("tm-zero-day")).toContainText(
    "4 reports give the same day",
  );
  await expect(page.getByTestId("tm-shape")).toBeVisible();
  await expect(page.getByTestId("tm-subset-caveat")).toHaveText(
    m.onset.subsetCaveat,
  );
  await expect(page.getByTestId("tm-agreement")).toHaveText(m.agreement.agrees);
  await expect(page.getByTestId("tm-compare")).toBeVisible();
  await expect(page.getByTestId("tm-gate")).toContainText("7 to 104 days");
  await page.getByTestId("tm-curve").getByText(m.table).click();
  await expect(
    page.getByTestId("tm-curve-table").locator("tbody tr"),
  ).toHaveCount(12);
  // Validation on the index: every verdict shown, including the failures.
  await page.goto("/en/research/time-machine");
  const val = page.getByTestId("tm-validation");
  await expect(val).toContainText("1 credible, 1 borderline, 0 failed");
  await expect(val).toContainText("0 credible, 1 borderline, 3 failed");
  await val.getByText(/^PBPK \(httk\)/).click();
  await expect(
    page.locator(
      '[data-testid=tm-validation-pbpk] tr[data-credibility="failed"]',
    ),
  ).toHaveCount(3);

  // Antipsychotics: small sample → no shape class; PBPK populations as bands with a table.
  await page.goto(
    "/en/research/time-machine/cascade#antipsychotic_eps_antiparkinson",
  );
  await expect(page.getByTestId("tm-css")).toBeVisible();
  await expect(page.getByTestId("tm-small-sample")).toHaveText(
    m.onset.smallSample,
  );
  await expect(page.getByTestId("tm-shape")).toHaveCount(0);
  await expect(page.locator("main")).not.toContainText(
    m.onset.shapeClass.early,
  );
  await expect(page.getByTestId("tm-gate")).toContainText(m.gate.small);
  await page.getByTestId("tm-css").getByText(m.table).click();
  await expect(
    page.getByTestId("tm-css-table").locator("tbody tr"),
  ).toHaveCount(4);

  // Rhubarb: compartmental model validated, no potency → the recorded gap, not a verdict.
  await page.goto("/en/research/time-machine/substance#rhubarb");
  await expect(page.getByTestId("tm-model-label")).toHaveText(
    m.method.compartmental,
  );
  await expect(page.getByTestId("tm-no-potency")).toHaveText(
    m.reasons.no_potency,
  );
  await expect(page.getByTestId("tm-verdict")).toHaveCount(0);
  await expect(page.locator("main")).not.toContainText(/PBPK/);
  // Anise: no human PK → the reason in place of any verdict.
  await page.goto("/en/research/time-machine/substance#anise");
  await expect(page.getByTestId("tm-not-validated")).toHaveText(
    m.reasons.no_pk,
  );
});

test("states: 503 not installed with retry, unknown id", async ({ page }) => {
  await stubApi(page, {
    "/timemachine/catalogue": {
      status: 503,
      body: { error: "time_machine_not_installed" },
    },
  });
  await page.goto("/en/research/time-machine");
  await expect(page.getByRole("alert").filter({ hasText: /\w/ })).toContainText(
    messages.en.TimeMachine.errors.unavailable,
  );
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await page.unrouteAll();
  await stubApi(page, {
    ...stubs(),
    "/timemachine/substance/nope": {
      status: 404,
      body: { error: "unknown_substance" },
    },
  });
  await page.goto("/en/research/time-machine/substance#nope");
  await expect(page.getByRole("alert").filter({ hasText: /\w/ })).toContainText(
    messages.en.TimeMachine.errors.unknown,
  );
});

test("demo mode: recorded answers, no request at all", async ({ page }) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  const requests = recordRequests(page);
  await page.goto("/en/research/time-machine");
  await expect(page.getByTestId("tm-demo")).toBeVisible();
  await page.getByRole("link", { name: /Rhubarb/ }).click();
  await expect(page.getByTestId("tm-exposure-card")).toBeVisible();
  expect(requests.filter((r) => r.url().includes("/api/"))).toEqual([]);
});

test("patient flow: the timing sentence in the amlodipine finding only (design §10.5)", async ({
  page,
}) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  const m = messages.en.TimeMachine.patient;
  await page.goto("/en/results");
  const cards = page.locator('a[href*="/results/finding#"]');
  await expect(cards.first()).toBeVisible();
  const hrefs = [
    ...new Set(
      await cards.evaluateAll((as) => as.map((a) => a.getAttribute("href")!)),
    ),
  ];
  let shown = 0;
  for (const href of hrefs) {
    await page.goto(href);
    await expect(
      page.getByRole("link", { name: messages.en.Findings.makeNote }),
    ).toBeVisible();
    await page.waitForLoadState("networkidle");
    const n = await page.getByTestId("tm-patient-sentence").count();
    if (n) {
      shown++;
      const s = page.getByTestId("tm-patient-sentence");
      await expect(s).toContainText(
        m.sentence
          .replace("{event}", "Swollen ankles or legs (peripheral edema)")
          .replace("{drug}", "amlodipine")
          .replace("{start}", "7")
          .replace("{end}", "104"),
      );
      await expect(s).toContainText(m.review);
      await expect(s).not.toContainText(/mg|µmol|PBPK|Weibull|%/);
    }
  }
  expect(shown).toBe(1);
});

test("links: séance substance and cascade-map rule open the time machine", async ({
  page,
}) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  await page.goto("/en/research/seance");
  const link = page.getByTestId("seance-time-machine");
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(
    /\/research\/time-machine\/substance#st_johns_wort$/,
  );
  await expect(page.getByTestId("tm-constituents")).toBeVisible();

  await page.goto("/en/cascades");
  await page.getByRole("button", { name: "List", exact: true }).click();
  await page.getByTestId("row-5").getByRole("button").click();
  await expect(page.getByTestId("cm-time-machine")).toHaveAttribute(
    "href",
    /\/research\/time-machine\/cascade#amlodipine_oedema_diuretic$/,
  );
  await page
    .getByTestId("cm-panel")
    .getByRole("button", { name: "Close" })
    .click();
  await page.getByTestId("row-18").getByRole("button").click();
  await expect(page.getByTestId("cm-time-machine")).toHaveCount(2);
});

// report-assistant Req 2–10: from a finding to a draft (copy all, the exact official href), the
// region switch, the doctor demo page to a draft, print media, no request to /api or another
// origin (demo and live), and C1–C3 at both viewports (projects), in both themes and every locale
// (E2E_LOCALES respected).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page, type Request } from "@playwright/test";

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
  THEMES,
  useTheme,
} from "./helpers";

const read = (...p: string[]) =>
  JSON.parse(readFileSync(join(import.meta.dirname, ...p), "utf8"));
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read("../messages", `${l}.json`)]),
);
const channels = read("../src/report/channels.json") as {
  id: string;
  url: string;
}[];
const url = (id: string) => channels.find((c) => c.id === id)!.url;
const en = messages.en.ReportAssistant;
const vocab = read("../src/vocabulary/en.json");

const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

const demo = (page: Page) =>
  page.addInitScript(() => sessionStorage.setItem("janus.v1.demo", "istanbul"));

/** Req 6.1: nothing to /api, nothing to another origin. */
function expectNothingSent(page: Page, requests: Request[]) {
  const origin = new URL(page.url()).origin;
  expect(
    requests
      .map((r) => r.url())
      .filter(
        (u) =>
          !u.startsWith("data:") &&
          !u.startsWith("blob:") &&
          (new URL(u).origin !== origin ||
            new URL(u).pathname.startsWith("/api/")),
      ),
  ).toEqual([]);
}

async function expectExternal(page: Page, href: string) {
  const open = page.getByTestId("report-open");
  await expect(open).toHaveAttribute("href", href);
  await expect(open).toHaveAttribute("target", "_blank");
  await expect(open).toHaveAttribute("rel", "noopener noreferrer");
}

test("from a finding to a draft: copy all and the official form", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await demo(page);
  const requests = recordRequests(page);
  await page.goto("/en/results/finding#0");
  await page
    .getByRole("link", { name: en.link })
    .filter({ visible: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/en\/report#src=finding&ing=Q668093/);
  const draft = page.getByTestId("report-draft");
  await expect(draft).toBeVisible();
  // Istanbul: region TR, TÜFAM e-form first; the demo stamp is on the draft.
  await expect(page.getByRole("radio", { name: "Türkiye" })).toBeChecked();
  await expect(page.getByTestId("report-demo")).toHaveText(en.draft.demo);
  await expect(page.getByTestId("report-not-sent")).toHaveText(en.summary);
  await expectExternal(page, "https://vigiflow-eforms.who-umc.org/tr/tr");
  const event = vocab.events.myalgia_myositis.label as string;
  await expect(draft.getByTestId("report-value").first()).toHaveText(event);
  await expect(draft.getByTestId("report-label").first()).toHaveText(
    "Reaksiyon/belirti",
  );
  await expect(
    draft.getByText("Atordem 20 (demo) (atorvastatin)"),
  ).toBeVisible();
  // The outcome uses the form's own options.
  await page.getByRole("radio", { name: /İyileşiyor\/düzeliyor/ }).check();
  // Untick one other medicine: the draft holds exactly the ticked ones.
  await page.getByRole("checkbox", { name: "Furodem 40 (demo)" }).uncheck();
  const others = draft.locator(
    '[data-key="others"] [data-testid="report-value"]',
  );
  await expect(others).not.toContainText("Furodem");
  await expect(others).toContainText("Amlodis Plus 10/20 (demo)");
  await page.getByRole("button", { name: en.draft.copyAll }).click();
  await expect(
    page.getByRole("status").filter({ hasText: en.draft.copiedAll }),
  ).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  const lines = copied.split("\n");
  expect(lines[0]).toBe(en.draft.demo);
  expect(lines[1]).toBe(
    `Reaksiyonlar/belirtiler > Reaksiyon/belirti: ${event}`,
  );
  expect(copied).toContain(
    "Reaksiyonlar/belirtiler > Sonuç: İyileşiyor/düzeliyor",
  );
  expect(copied).toContain(
    "İlaçlar > İlaç adı: Atordem 20 (demo) (atorvastatin)",
  );
  expect(copied).not.toContain("Furodem");
  // Copy one field.
  await draft.getByRole("button", { name: `Copy Reaksiyon/belirti` }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(event);
  expectNothingSent(page, requests);
});

test("region switch: each region opens its verified form", async ({ page }) => {
  await demo(page);
  const requests = recordRequests(page);
  await page.goto("/en/report#src=list");
  await expect(page.getByTestId("report-draft")).toBeVisible();
  await page.getByRole("radio", { name: "United States" }).check();
  await expectExternal(page, url("us-fda-3500b-online"));
  await expect(page.getByTestId("report-channel-note")).toHaveText(
    en.channel.borrowed,
  );
  await page.getByRole("radio", { name: en.where.kind.pdf }).check();
  await expectExternal(
    page,
    "https://www.fda.gov/media/85598/download?attachment",
  );
  await expect(page.getByTestId("report-label").first()).toHaveText(
    "C1 Name(s) of the product as it appears on the box, bottle, or package",
  );
  await page.getByRole("radio", { name: "European Union" }).check();
  await expectExternal(page, url("de-bund-online"));
  await expect(page.getByTestId("report-channel-note")).toHaveText(
    en.channel.noFields.partial,
  );
  await page.getByRole("radio", { name: en.where.countries.FR }).check();
  await expectExternal(
    page,
    "https://signalement.social-sante.gouv.fr/espace-declaration/guidage?profil=USAGER",
  );
  await page.getByRole("radio", { name: en.where.countries.ES }).check();
  await expectExternal(page, url("es-notificaram-ciudadano"));
  await page.getByRole("radio", { name: en.where.countries.EU }).check();
  await expectExternal(page, url("eu-ema-guidance"));
  await expect(page.getByTestId("finder-link")).toHaveAttribute(
    "href",
    "https://www.adrreports.eu/en/national.html",
  );
  await page.getByRole("radio", { name: "Türkiye" }).check();
  await expect(
    page.getByRole("link", { name: /tufam@titck\.gov\.tr/ }),
  ).toHaveAttribute("href", "mailto:tufam@titck.gov.tr");
  await expect(
    page.getByRole("link", { name: /0 800 314 00 08/ }),
  ).toHaveAttribute("href", "tel:+908003140008");
  // Every href on the page is the app's own, a CSV address or the cited DOI.
  const known = new Set(channels.flatMap((c) => [c.url]));
  for (const href of await page
    .locator('a[target="_blank"]')
    .evaluateAll((as) => as.map((a) => a.getAttribute("href")!)))
    expect(
      known.has(href) ||
        href.startsWith("https://doi.org/") ||
        read("../src/report/channels.json").some(
          (c: { sourceUrl: string }) => c.sourceUrl === href,
        ),
      href,
    ).toBe(true);
  expectNothingSent(page, requests);
});

test("doctor demo page: the per-finding link opens a prefilled draft", async ({
  page,
}) => {
  await demo(page);
  const requests = recordRequests(page);
  await page.goto("/en/demo/doctor");
  const link = page.getByTestId("doctor-report-link").first();
  await expect(link).toHaveAttribute("target", "_blank");
  const href = (await link.getAttribute("href"))!;
  expect(href).toMatch(
    /^\/tr\/report#src=doctor&rule=pipc%3A9&ing=Q668093&with=/,
  );
  expect(href).toContain("demo=1");
  // The new tab has no demo session (noopener): the fragment's demo flag labels the draft.
  await page.evaluate(() => sessionStorage.clear());
  await page.goto(href.replace("/tr/", "/en/"));
  await expect(page.getByTestId("report-hcp")).toBeVisible();
  await expect(page.getByText(en.hcp.prefilled)).toBeVisible();
  await expect(page.getByTestId("report-ingredient")).toContainText(
    "atorvastatin",
  );
  await expect(page.getByTestId("report-demo-top")).toHaveText(en.draft.demo);
  await page.getByRole("radio", { name: "Türkiye" }).check();
  await expect(page.getByTestId("report-hcp")).toContainText(
    "Advers Reaksiyon Bildirim Formu",
  );
  await expect(page.getByTestId("report-value").first()).toHaveText(
    vocab.events.myalgia_myositis.label,
  );
  expectNothingSent(page, requests);
});

test("live mode: an empty list, typed values, nothing sent", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem(
      "janus.v1.settings",
      JSON.stringify({ v: 1, userRegion: "US" }),
    ),
  );
  const requests = recordRequests(page);
  await page.goto("/en/report");
  await expect(page.getByText(en.what.noList)).toBeVisible();
  await expect(page.getByText(en.draft.empty)).toBeVisible();
  await page.getByLabel(en.what.box).fill("Example 10 mg");
  await page
    .getByRole("textbox", { name: new RegExp(`^${en.what.eventText}`) })
    .fill("Rash on both arms");
  await expect(page.getByTestId("report-demo")).toHaveCount(0);
  await expect(page.getByTestId("report-value")).toHaveText([
    "Rash on both arms",
    "Example 10 mg",
  ]);
  expectNothingSent(page, requests);
});

test("print: only the draft, with the not-sent sentence and the disclaimer", async ({
  page,
}) => {
  await demo(page);
  await page.goto("/en/report#src=list");
  await expect(page.getByTestId("report-draft")).toBeVisible();
  await page.emulateMedia({ media: "print" });
  const draft = page.getByTestId("report-draft");
  await expect(draft).toBeVisible();
  await expect(draft.getByTestId("report-not-sent")).toBeVisible();
  await expect(draft.getByText(messages.en.Disclaimer.text)).toBeVisible();
  await expect(draft.getByTestId("report-demo")).toBeVisible();
  await expect(page.getByTestId("report-open")).toBeHidden();
  await expect(page.getByTestId("disclaimer")).toBeHidden();
  await expect(page.getByTestId("emergency-notice")).toBeHidden();
  await expect(
    page.getByRole("button", { name: en.draft.copyAll }),
  ).toBeHidden();
});

for (const theme of THEMES)
  for (const locale of locales)
    test(`checks, ${locale}, ${theme}`, async ({ page }) => {
      await useTheme(page, theme);
      await demo(page);
      const requests = recordRequests(page);
      const m = messages[locale].ReportAssistant;
      for (const hash of [
        "src=list",
        "src=finding&ing=Q668093&event=myalgia_myositis&items=3",
      ]) {
        await page.goto(`/${locale}/report#${hash}`);
        await expect(page.getByTestId("report-draft")).toBeVisible();
        await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
        await expect(
          page.locator("main [data-testid]").first(),
        ).toHaveAttribute("data-testid", "emergency-notice");
        await expect(page.getByRole("heading", { level: 1 })).toHaveText(
          m.title,
        );
        await expect(page.getByTestId("report-not-sent")).toHaveText(m.summary);
        await expect(page.getByTestId("under-reporting")).toHaveText(
          m.intro.fact,
        );
        await expect(page.getByTestId("demo-label")).toBeVisible();
        await expectNoAxeViolations(page);
        await expectNoHorizontalScroll(page);
        await expectTouchTargets(page);
        const text = await page.locator("body").innerText();
        expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual(
          [],
        );
        if (theme === "glass")
          expect(findForbiddenPhrases(text, themeWords[locale])).toEqual([]);
      }
      // The EU with its countries and the US form, for long labels at 375 px.
      await page
        .getByRole("radio", { name: messages[locale].Common.region.EU })
        .check();
      await page.getByRole("radio", { name: m.where.countries.ES }).check();
      await expectNoHorizontalScroll(page);
      await page
        .getByRole("radio", { name: messages[locale].Common.region.US })
        .check();
      await page.getByRole("radio", { name: m.where.kind.pdf }).check();
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      expectNothingSent(page, requests);
    });

test("3500B E10 / E11: known prescription types go to E11, unknown types are named (DP13)", async ({
  page,
}) => {
  const e11 =
    "E11 List all current prescription medications and medical devices being used";
  const requests = recordRequests(page);
  // Ohio: four US products, all "HUMAN PRESCRIPTION DRUG" in the recorded openFDA data.
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "ohio"),
  );
  await page.goto("/en/report#src=list");
  await expect(page.getByTestId("report-draft")).toBeVisible();
  await page.getByRole("radio", { name: "United States" }).check();
  await page.getByRole("radio", { name: en.where.kind.pdf }).check();
  await expect(page.getByTestId("report-label")).toContainText([e11]);
  await expect(page.getByTestId("report-type-unknown")).toHaveCount(0);
  expectNothingSent(page, requests);
});

test("3500B E10 / E11: products without a US type stay under E11 and the draft says so (DP13)", async ({
  page,
}) => {
  await demo(page);
  await page.goto("/en/report#src=list");
  await expect(page.getByTestId("report-draft")).toBeVisible();
  await page.getByRole("radio", { name: "United States" }).check();
  await page.getByRole("radio", { name: en.where.kind.pdf }).check();
  const note = page.getByTestId("report-type-unknown");
  await expect(note).toBeVisible();
  await expect(note).toContainText("E11");
  await expect(note).toContainText("E10");
  await expect(page.getByTestId("report-label")).not.toContainText([/^E10 /]);
});

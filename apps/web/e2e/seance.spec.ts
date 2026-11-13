// Séance screen (séance design §7.3, Req 7; experience Req 4.4, 6.4, 24): the API stubbed from
// synthetic answers (src/test/fixtures/seance.ts and light.ts), never from the recorded files; demo
// mode (bundled recorded file) is checked for structure only. C1–C3 in 5 locales ×
// 2 themes, the three seats, labels and states, demo mode without any request, the cross-reference
// from a hypothesis card, and screenshots at 375 and 1280 px in both themes.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { lightSet } from "../src/test/fixtures/light";
import { seanceSet } from "../src/test/fixtures/seance";
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

type Pair = { substance: string; condition: string };
type Answer = Record<string, unknown> & {
  substance: Record<string, unknown>;
  witnesses: Record<string, Record<string, unknown>>;
};
const read = (p: string) =>
  JSON.parse(readFileSync(join(import.meta.dirname, p), "utf8"));
const fx = seanceSet() as unknown as {
  catalogue: unknown;
  pairs: { request: Pair; answer: Answer }[];
};
const light = lightSet();
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../messages/${l}.json`)]),
);
const SHOTS = process.env.SEANCE_SHOTS_DIR;
const answerFor = (p: Pair | null) =>
  fx.pairs.find(
    (x) =>
      x.request.substance === p?.substance &&
      x.request.condition === p?.condition,
  )?.answer;

async function stubSeance(page: Page, edit: (a: Answer) => Answer = (a) => a) {
  return stubApi(page, {
    "/seance/catalogue": { body: fx.catalogue },
    "/seance/pair": (body) => {
      const a = answerFor(body as Pair | null);
      return a
        ? { body: edit(structuredClone(a)) }
        : { status: 503, body: { error: "seance_unavailable" } };
    },
  });
}

const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

for (const theme of THEMES)
  for (const locale of locales)
    test(`séance route, ${locale}, ${theme}`, async ({ page }, info) => {
      await useTheme(page, theme);
      await stubSeance(page);
      await page.goto(`/${locale}/research/seance`);
      const m = messages[locale].Seance;
      await expect(page.getByTestId("seance-table")).toBeVisible();
      await expect(page.getByTestId("disclaimer")).toHaveText(
        messages[locale].Disclaimer.text,
      );
      await expect(page.getByTestId("rule7")).toHaveText(m.framing);
      await expect(page.getByTestId("seance-review")).toHaveText(m.review);
      await expect(page.locator("h1")).toHaveText(
        m.title[theme === "glass" ? "glass" : "twoFaces"],
      );
      for (const pair of ["st_johns_wort", "vinegar"]) {
        await page.getByLabel(m.pick.substance).selectOption(pair);
        if (pair === "vinegar")
          await page
            .getByRole("radio", { name: new RegExp(m.condition.infection) })
            .check();
        await expect(page.locator("#seance-substance")).toContainText(
          pair === "vinegar" ? "vinegar" : "St John's wort",
        );
        await page.waitForLoadState("networkidle");
        await expectNoAxeViolations(page);
        await expectNoHorizontalScroll(page);
        await expectTouchTargets(page);
        const text = await page.locator("body").innerText();
        expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual(
          [],
        );
        if (theme === "glass")
          expect(findForbiddenPhrases(text, themeWords[locale])).toEqual([]);
        if (SHOTS && (locale === "en" || pair === "st_johns_wort")) {
          mkdirSync(SHOTS, { recursive: true });
          if (locale === "en")
            await page.screenshot({
              path: join(
                SHOTS,
                `seance-${pair}-${info.project.name}-${theme}.png`,
              ),
              fullPage: true,
            });
        }
      }
    });

test("three seats, labels, locator, count and missing witness", async ({
  page,
}) => {
  await stubSeance(page);
  await page.goto("/en/research/seance");
  const table = page.getByTestId("seance-table");
  await expect(table.getByRole("listitem").first()).toBeVisible();
  const seats = page.locator("[data-testid^=seat-]");
  await expect(seats).toHaveCount(3);
  await expect(seats.nth(0)).toHaveAttribute("data-testid", "seat-past");
  await expect(seats.nth(1)).toHaveAttribute("data-testid", "seat-present");
  await expect(seats.nth(2)).toHaveAttribute("data-testid", "seat-science");
  await expect(page.getByTestId("witness-count")).toHaveText(
    "2 of 3 witnesses",
  );
  await expect(page.getByTestId("missing-witnesses")).toHaveText(
    "Missing witnesses: the present",
  );
  await expect(page.getByTestId("seat-present")).toContainText(
    "No FAERS link for this substance.",
  );
  await expect(page.getByText("Identified (matches PMC3941892)")).toBeVisible();
  const arabic = page.getByTestId("arabic-span").first();
  await expect(arabic).toHaveAttribute("lang", "ar");
  await expect(arabic).toHaveAttribute("dir", "rtl");
  const items = await page.getByTestId("arabic-span").count();
  await expect(page.getByTestId("mt-label")).toHaveCount(items);
  await expect(page.getByTestId("review-label")).toHaveCount(items);
  await expect(page.getByTestId("review-label").first()).toHaveText(
    "Expert review has not yet been done",
  );
  await expect(page.getByTestId("locator").first()).toHaveText(
    "Canon, Book 2, entry h0219, page V01P447, lines 12231–12232 (OpenITI)",
  );
  await expect(page.getByTestId("seat-science")).toContainText(
    "Randomised controlled trial",
  );
  await expect(page.getByTestId("framing")).toHaveText(
    "Candidate worth investigating — not a treatment.",
  );
  // the count is a count: no percentage, no score
  await expect(page.locator("main")).not.toContainText(/%|score:/i);

  await page.getByLabel("Substance").selectOption("vinegar");
  await page.getByRole("radio", { name: /Wound and skin infection/ }).check();
  const present = page.getByTestId("seat-present");
  await expect(present).toContainText(
    "Too few FAERS reports to look for a pattern.",
  );
  await expect(present).toContainText(
    "0 reports with one of the condition's terms, among 59 FAERS reports",
  );
  await expect(present).toContainText("Counts are reports, not people.");
  await expect(present).toContainText("not the substance itself");
  await expect(page.getByText(/no concept of infection/)).toBeVisible();
});

test("states: 503, zero witnesses and a hazardous substance", async ({
  page,
}) => {
  await stubApi(page, {
    "/seance/catalogue": { status: 503, body: { error: "seance_unavailable" } },
  });
  await page.goto("/en/research/seance");
  await expect(page.getByRole("alert").filter({ hasText: /\w/ })).toContainText(
    messages.en.Seance.errors.unavailable,
  );
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();

  await page.unrouteAll();
  await stubSeance(page, (a) => {
    for (const w of ["past", "present", "science"]) {
      a.witnesses[w]!.supports = false;
      a.witnesses[w]!.items = [];
      a.witnesses[w]!.confidence = "none";
    }
    a.witnesses.past!.missing_reason = "no_canon_passage";
    a.witnesses.science!.missing_reason = "no_citable_study";
    a.witnesses.science!.excluded = ["paper:x"];
    a.supporting_witnesses = 0;
    a.missing_witnesses = ["past", "present", "science"];
    a.substance.hazard = "toxic";
    a.headline = { eligible: false, reasons: ["hazardous_substance"] };
    return a;
  });
  await page.goto("/en/research/seance");
  await expect(page.getByTestId("witness-count")).toHaveText(
    "0 of 3 witnesses",
  );
  await expect(page.getByTestId("missing-witnesses")).toHaveText(
    "No witness speaks for this pair in this data.",
  );
  await expect(page.getByTestId("hazard")).toHaveText(
    "Historical record only — toxic substance.",
  );
  await expect(page.getByTestId("science-excluded")).toContainText(
    "1 listed study was removed by Evidence Integrity",
  );
  await expect(
    page.getByText(
      "Not shown as a demo example: the substance is flagged as toxic",
    ),
  ).toBeVisible();
  await expectNoAxeViolations(page);
});

// Demo mode reads the bundled recorded file. Its content changes with every release, so this
// checks structure only (the file is checked in src/test/recorded-contract.test.ts).
test("demo mode answers from the bundled file without any request", async ({
  page,
}) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  const all = recordRequests(page);
  await page.goto("/en/research/seance");
  await expect(page.getByTestId("seance-demo")).toBeVisible();
  await expect(page.getByTestId("witness-count")).toBeVisible();
  expect(
    await page.getByLabel("Substance").locator("option").count(),
  ).toBeGreaterThan(0);
  expect(
    all.filter((r) => new URL(r.url()).pathname.startsWith("/api/")),
  ).toEqual([]);
});

test("a hypothesis card of the same ingredient opens the séance on that pair", async ({
  page,
}) => {
  const cards = structuredClone(light.cards.alopecia);
  cards.cards[0]!.ingredient.key = "Q47512"; // acetic acid, the component of vinegar
  await stubApi(page, {
    "/light/overview": { body: light.overview },
    "/light/cards": () => ({ body: cards }),
    "/seance/catalogue": { body: fx.catalogue },
    "/seance/pair": (body) => {
      const a = answerFor(body as Pair | null);
      return a
        ? { body: a }
        : { status: 503, body: { error: "seance_unavailable" } };
    },
  });
  await page.goto("/en/research/hypotheses");
  // the link keeps the pair in memory: click once the page is interactive
  await page.waitForLoadState("networkidle");
  const card = page.getByTestId("hypothesis-card").first();
  await card.locator("details summary").click();
  const links = card.getByTestId("seance-links");
  await expect(links).toContainText("Also at the séance table");
  await expect(links).toContainText("a component of a substance in the Canon");
  await links
    .getByRole("link", { name: "vinegar: Wound and skin infection" })
    .click();
  await expect(page).toHaveURL(/\/en\/research\/seance$/);
  await expect(page.locator("#seance-substance")).toContainText("vinegar");
  await expect(
    page.getByRole("radio", { name: /Wound and skin infection/ }),
  ).toBeChecked();
  // no other card shows a link (sodium chloride is a different exposure)
  await page.goBack();
  await expect(page.getByTestId("seance-links")).toHaveCount(1);
});

// Medicine information in the interface language (plain-medicine-info Req 5): the page reached
// from the medicine list. The API is stubbed with what the API tests produce: the group answers
// of src/demo/plain-info.recorded.json (five languages) and the official parts of
// src/plaininfo/fixtures/info.json (invented products). C1-C3 in five locales × two themes; the
// request holds codes and the product's own code or published name only; no information, error
// with retry, large text, demo mode with no request. Screenshots when PLAININFO_SHOTS_DIR is set.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "../src/i18n/forbidden-phrases";
import { reassurance } from "../src/i18n/reassurance";

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
const answers = read("../src/plaininfo/fixtures/info.json");
const recorded = read("../src/demo/plain-info.recorded.json");
const noRecall = {
  ...read("../src/recall/fixtures/check.json"),
  matches: [],
  total_matches: 0,
};
const ohio = read("../src/demo/fixtures/ohio.json");
const istanbul = read("../src/demo/fixtures/istanbul.json");
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../messages/${l}.json`)]),
);
const SHOTS = process.env.PLAININFO_SHOTS_DIR;
const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

type Body = {
  language: string;
  ingredients: { atc_codes: string[] }[];
  product?: { country: string; ndc?: string; name?: string };
};

/** The API's answer for a request: recorded group answers, and the fixture's official part. */
function answerFor(body: Body) {
  const official =
    body.product?.country === "US"
      ? answers.us.official
      : body.product?.country === "FR"
        ? answers.fr.official
        : null;
  return {
    body: {
      language: body.language,
      groups_version: recorded.groups_version,
      ingredients: body.ingredients.map(
        (i) => recorded.ingredients[body.language][i.atc_codes.join(" ")],
      ),
      official,
      official_status: official
        ? official.kind === "label_text"
          ? "text"
          : "page"
        : body.product
          ? "not_found"
          : "not_asked",
      notices: ["no_dose_information"],
      disclaimer: answers.us.disclaimer,
    },
  };
}

const item = (
  id: string,
  from: { resolution: { dataset_version: string; candidates: unknown[] } },
  over: Record<string, unknown>,
  box: string,
) => ({
  id,
  sourceKey: { kind: "ndc", ndc: "99999-123-30" },
  datasetVersion: from.resolution.dataset_version,
  candidate: { ...(from.resolution.candidates[0] as object), ...over },
  choices: [],
  started: "2025-03",
  boxName: box,
  needsConfirmation: false,
});
// Ohio item 0 (lisinopril, an ACE inhibitor) with an invented package; the box carries a lot.
const usItem = {
  ...item(
    "us-1",
    ohio.items[0],
    {
      product_name: "Exampletine 10 mg tablets (invented)",
      brand_name: "Exampletine 10 mg tablets (invented)",
      packages: [{ ndc_published: "99999-123-30", ndc11: "99999012330" }],
    },
    "ZZBOX my blood pressure tablets",
  ),
  lot: "AB-1234",
};
// Istanbul item 0 (amlodipine + lisinopril) as a French product; item 1 as a Turkish one.
const frItem = item(
  "fr-1",
  istanbul.items[0],
  {
    region: "EU",
    country: "FR",
    product_name: "EXEMPLINE 10 mg, comprimé (inventé)",
    source: {
      ...ohio.items[0].resolution.candidates[0].source,
      source_id: "eu_fr_bdpm",
      region: "EU",
    },
  },
  "ZZBOX boîte de France",
);
const seed = (
  page: Page,
  items: unknown[],
  settings?: Record<string, unknown>,
) =>
  page.addInitScript(
    ([list, extra]) => {
      localStorage.setItem(
        "janus.v1.list",
        JSON.stringify({ v: 1, items: list }),
      );
      if (extra) {
        const raw = localStorage.getItem("janus.v1.settings");
        localStorage.setItem(
          "janus.v1.settings",
          JSON.stringify({ ...(raw ? JSON.parse(raw) : { v: 1 }), ...extra }),
        );
      }
    },
    [items, settings ?? null] as const,
  );
const infoBodies = (seen: { url(): string; postDataJSON(): unknown }[]) =>
  seen
    .filter((r) => r.url().endsWith("/api/medicine-info"))
    .map((r) => r.postDataJSON() as Body);

async function shot(page: Page, name: string, project: string) {
  if (!SHOTS) return;
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({
    path: join(SHOTS, `${name}-${project}.png`),
    fullPage: true,
  });
}

/** The page text without the quoted label (the company's words, in English). */
async function ownText(page: Page) {
  return page.evaluate(() => {
    const main = document.querySelector("main")!.cloneNode(true) as HTMLElement;
    main.querySelectorAll("blockquote").forEach((q) => q.remove());
    return main.innerText;
  });
}

for (const locale of locales)
  for (const theme of THEMES)
    test(`US product: group sentence and quoted label, ${locale}, ${theme}`, async ({
      page,
    }, info) => {
      const m = messages[locale].PlainInfo;
      await useTheme(page, theme);
      await seed(page, [usItem]);
      const requests = recordRequests(page);
      const seen = await stubApi(page, {
        "/recalls/check": { body: noRecall },
        "/medicine-info": (body) => answerFor(body as Body),
      });
      await page.goto(`/${locale}/medicines`);
      await page.getByRole("link", { name: m.link }).click();
      await expect(page).toHaveURL(
        new RegExp(`/${locale}/medicines/info#us-1$`),
      );

      const group = recorded.ingredients[locale]["C09AA03"].groups[0];
      const card = page.getByTestId("plain-info-group");
      await expect(card).toHaveCount(1);
      await expect(card.getByTestId("plain-info-sentence")).toHaveText(
        group.text,
      );
      await expect(card).toContainText(group.name);
      await expect(card).toContainText("C09AA03");
      await expect(card.getByTestId("plain-info-review")).toHaveText(m.review);
      await expect(page.getByTestId("plain-info-method")).toHaveText(m.method);
      await expect(page.getByTestId("plain-info-limits")).toContainText(
        m.limits.ask,
      );
      await expect(page.getByTestId("plain-info-limits")).toContainText(
        m.limits.dose,
      );
      await expect(page.getByTestId("plain-info-nothing")).toHaveCount(0);

      // The official text: a quotation in English, unchanged, marked as not translated.
      const quote = page.getByTestId("plain-info-quote");
      await expect(quote).toHaveAttribute("lang", "en");
      expect(
        await quote
          .locator("p")
          .evaluateAll((ps) => ps.map((p) => p.textContent)),
      ).toEqual(answers.us.official.paragraphs);
      await expect(page.getByTestId("plain-info-not-translated")).toHaveText(
        m.official.us.language,
      );
      await expect(
        page.getByRole("link", { name: m.official.us.open }),
      ).toHaveAttribute("href", answers.us.official.url);

      // One request: the language, the codes and the product code. Nothing else of the item.
      expect(infoBodies(seen)).toEqual([
        {
          language: locale,
          ingredients: [{ atc_codes: ["C09AA03"] }],
          product: { country: "US", ndc: "99999-0123" },
        },
      ]);
      for (const r of requests) {
        expect(r.url()).not.toMatch(/us-1|ZZBOX|1234/);
        expect(r.postData() ?? "").not.toMatch(/ZZBOX|AB-?1234|us-1|2025-03/i);
      }

      // The emergency notice comes first; red is used nowhere else.
      const first = await page
        .locator("main [data-testid]")
        .first()
        .getAttribute("data-testid");
      expect(first).toBe("emergency-notice");
      await expect(page.getByTestId("disclaimer")).toHaveText(
        messages[locale].Disclaimer.text,
      );
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      const text = await ownText(page);
      expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
      expect(findForbiddenPhrases(text, reassurance[locale])).toEqual([]);
      await shot(page, `us-${locale}-${theme}`, info.project.name);
    });

for (const locale of locales)
  test(`French product: two ingredients and the product page, ${locale}`, async ({
    page,
  }, info) => {
    const m = messages[locale].PlainInfo;
    await seed(page, [frItem]);
    const seen = await stubApi(page, {
      "/medicine-info": (body) => answerFor(body as Body),
    });
    await page.goto(`/${locale}/medicines/info#fr-1`);
    await expect(page.getByTestId("plain-info-ingredient")).toHaveCount(2);
    await expect(page.getByTestId("plain-info-sentence")).toHaveText([
      recorded.ingredients[locale]["C08CA01"].groups[0].text,
      recorded.ingredients[locale]["C09AA03"].groups[0].text,
    ]);
    await expect(page.getByTestId("plain-info-review")).toHaveCount(2);
    const official = page.getByTestId("plain-info-official");
    await expect(official).toHaveAttribute("data-kind", "product_page");
    await expect(official).toContainText(m.official.page.language.fr);
    await expect(
      official.getByRole("link", { name: m.official.page.open }),
    ).toHaveAttribute("href", answers.fr.official.url);
    await expect(page.locator("blockquote")).toHaveCount(0);
    expect(infoBodies(seen)).toEqual([
      {
        language: locale,
        ingredients: [{ atc_codes: ["C08CA01"] }, { atc_codes: ["C09AA03"] }],
        product: { country: "FR", name: "EXEMPLINE 10 mg, comprimé (inventé)" },
      },
    ]);
    await expectNoAxeViolations(page);
    await expectNoHorizontalScroll(page);
    await expectTouchTargets(page);
    await shot(page, `fr-${locale}`, info.project.name);
  });

for (const locale of locales)
  test(`no information is said clearly and is no statement, ${locale}`, async ({
    page,
  }, info) => {
    const m = messages[locale].PlainInfo;
    // Istanbul item 7: an ingredient outside the covered groups, on a Turkish box.
    const none = istanbul.items.findIndex(
      (i: {
        resolution: {
          candidates: { ingredients: { atc_codes: { code: string }[] }[] }[];
        };
      }) =>
        i.resolution.candidates[0]!.ingredients.every(
          (g) =>
            recorded.ingredients.en[
              g.atc_codes
                .map((a) => a.code)
                .sort()
                .join(" ")
            ]?.status === "none",
        ),
    );
    expect(none).toBeGreaterThanOrEqual(0);
    await seed(page, [
      item("tr-1", istanbul.items[none], {}, "Kutu (invented)"),
    ]);
    await stubApi(page, {
      "/medicine-info": (body) => answerFor(body as Body),
    });
    await page.goto(`/${locale}/medicines/info#tr-1`);
    const nothing = page.getByTestId("plain-info-nothing");
    await expect(nothing).toContainText(m.nothing.title);
    await expect(nothing).toContainText(m.nothing.body);
    await expect(page.getByTestId("plain-info-no-official")).toHaveText(
      m.official.none.country,
    );
    await expect(page.getByTestId("plain-info-sentence")).toHaveCount(0);
    await expect(page.getByTestId("plain-info-review")).toHaveCount(0);
    await expect(page.getByTestId("plain-info-limits")).toContainText(
      m.limits.ask,
    );
    const text = await ownText(page);
    expect(findForbiddenPhrases(text, reassurance[locale])).toEqual([]);
    expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
    await expectNoAxeViolations(page);
    await expectNoHorizontalScroll(page);
    await shot(page, `none-${locale}`, info.project.name);
  });

for (const theme of THEMES)
  test(`large text keeps the page inside the screen, ${theme}`, async ({
    page,
  }, info) => {
    await useTheme(page, theme);
    await seed(page, [usItem], { largeText: true });
    await stubApi(page, {
      "/medicine-info": (body) => answerFor(body as Body),
    });
    await page.goto("/de/medicines/info#us-1");
    await expect(page.getByTestId("plain-info-quote")).toBeVisible();
    expect(
      await page.evaluate(() =>
        parseFloat(getComputedStyle(document.documentElement).fontSize),
      ),
    ).toBeGreaterThan(16);
    await expectNoHorizontalScroll(page);
    await expectNoAxeViolations(page);
    await expectTouchTargets(page);
    await shot(page, `large-text-de-${theme}`, info.project.name);
  });

test("a long label text is cut, flagged and stays inside the page", async ({
  page,
}, info) => {
  await seed(page, [usItem]);
  await stubApi(page, {
    "/medicine-info": (body) => {
      const a = answerFor(body as Body);
      return { body: { ...a.body, official: answers.long.official } };
    },
  });
  await page.goto("/en/medicines/info#us-1");
  await expect(page.getByTestId("plain-info-official")).toContainText(
    "The section is longer than shown here. The full label has the rest.",
  );
  await expectNoHorizontalScroll(page);
  await expectNoAxeViolations(page);
  await shot(page, "long-en", info.project.name);
});

test("loading, then an error with a retry, then the answer", async ({
  page,
}, info) => {
  await seed(page, [usItem]);
  let calls = 0;
  await stubApi(page, {
    "/medicine-info": (body) =>
      ++calls === 1
        ? { status: 503, body: { error: "medicine_info_unavailable" } }
        : answerFor(body as Body),
  });
  await page.goto("/en/medicines/info#us-1");
  const error = page.getByRole("alert");
  await expect(error).toContainText(
    "The medicine information is not available right now. Please try again later.",
  );
  await expect(page.getByTestId("plain-info-ingredient")).toHaveCount(0);
  await expect(page.getByTestId("plain-info-nothing")).toHaveCount(0);
  await expectNoAxeViolations(page);
  await shot(page, "error", info.project.name);
  await error.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByTestId("plain-info-sentence")).toHaveCount(1);
  expect(calls).toBe(2);
});

test("a medicine that is not on the list gets a way back", async ({ page }) => {
  await seed(page, [usItem]);
  const seen = await stubApi(page);
  await page.goto("/en/medicines/info#no-such-item");
  await expect(
    page.getByText("This medicine is not on the list kept on this device."),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Back to the medicines" }),
  ).toBeVisible();
  expect(infoBodies(seen)).toEqual([]);
  await expectNoAxeViolations(page);
});

for (const locale of locales)
  test(`demo mode: group sentences from the recorded file, no request, ${locale}`, async ({
    page,
  }, info) => {
    const m = messages[locale].PlainInfo;
    const requests = recordRequests(page);
    await stubApi(page);
    await page.addInitScript(() =>
      sessionStorage.setItem("janus.v1.demo", "istanbul"),
    );
    await page.goto(`/${locale}/medicines`);
    await expect(page.getByRole("link", { name: m.link })).toHaveCount(
      istanbul.items.length,
    );
    await page.getByRole("link", { name: m.link }).first().click();
    await expect(page.getByTestId("demo-label")).toBeVisible();
    await expect(page.getByTestId("plain-info-sentence")).toHaveText([
      recorded.ingredients[locale]["C08CA01"].groups[0].text,
      recorded.ingredients[locale]["C09AA03"].groups[0].text,
    ]);
    await expect(page.getByTestId("plain-info-no-official")).toHaveText(
      m.official.none.demo,
    );
    expect(
      requests.filter((r) => new URL(r.url()).pathname.startsWith("/api/")),
    ).toEqual([]);
    await expectNoAxeViolations(page);
    await expectNoHorizontalScroll(page);
    await shot(page, `demo-${locale}`, info.project.name);
  });

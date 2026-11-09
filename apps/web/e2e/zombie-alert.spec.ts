// zombie-alert Req 2–7: the demo simulation (alert → updated note, no request at all), the live
// flow with a stubbed `/api/evidence/changes` (the check sends only a date), the notification
// permission asked only after a tap (mocked Notification), and C1–C3 for the alert, "What
// changed" and the Settings card at both viewports, in both themes and every locale (E2E_LOCALES).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { findForbiddenPhrases } from "../src/i18n/forbidden-phrases";
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

const read = (...p: string[]) =>
  JSON.parse(readFileSync(join(import.meta.dirname, ...p), "utf8"));
const messages = Object.fromEntries(
  LOCALES.map((l) => [l, read("../messages", `${l}.json`)]),
);
const fx = read("../src/demo/fixtures/istanbul.json");
const demoFx = read("../src/demo/fixtures/zombie.json");
const SOURCE = demoFx.change.evidence_id as string;
const SUPPORTING = "pipc:5:Q411347:Q388801:supporting";
const sentenceText = (lang: string, id: string) =>
  (
    fx.notes[lang].documents[0].sections
      .flatMap((s: { blocks: unknown[] }) => s.blocks)
      .find((b: { id?: string }) => b.id === id) as { text: string }
  ).text;
const supportingText = (lang: string) => sentenceText(lang, SUPPORTING);
/** The demo note is in the patient's note language (Istanbul: Turkish). */
const DEMO_LANG = fx.noteLanguage as string;

const EVIDENCE = fx.evidence[Object.keys(fx.evidence)[0]!];
/** A DOI-bearing item of the recorded resolution, as the template of the retracted one. */
const PAPER = EVIDENCE.items.find(
  (i: { id: string }) => i.id === "paper:bmj_2026:e100499",
);

const locales = process.env.E2E_LOCALES
  ? LOCALES.filter((l) => process.env.E2E_LOCALES!.split(",").includes(l))
  : LOCALES;

/**
 * C1 on the Zombie Alert cards only. The note screen's paper has a contrast finding of its own at
 * 1280 px in Two Faces (a medicine row past the A4 box), present without this feature: see the
 * tasks' open items.
 */
async function expectCardsAccessible(page: Page) {
  const r = await new AxeBuilder({ page })
    .include('[data-testid^="zombie-"]')
    .withTags([
      "wcag2a",
      "wcag2aa",
      "wcag21a",
      "wcag21aa",
      "wcag22a",
      "wcag22aa",
    ])
    .analyze();
  const summary = r.violations.map(
    (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`,
  );
  expect(summary, summary.join("\n")).toEqual([]);
}

/** Next.js keeps a visited route in the DOM, hidden: only the visible copy counts. */
const byId = (page: Page, id: string) =>
  page.getByTestId(id).filter({ visible: true });

async function settle(page: Page) {
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, {
    timeout: 15_000,
  });
}

async function demoNote(page: Page, locale: string) {
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  await page.goto(`/${locale}/note`);
  await settle(page);
  await page
    .getByRole("button", { name: messages[locale].Note.make, exact: true })
    .click();
  await expect(byId(page, "note-paper")).toBeVisible();
}

test("demo: simulate → alert on note and home → updated note shows what changed; no request", async ({
  page,
}) => {
  const requests = recordRequests(page);
  await demoNote(page, "en");
  const en = messages.en.ZombieAlert;
  await expect(byId(page, "zombie-alert")).toHaveCount(0);
  await page.getByRole("button", { name: en.simulate }).click();
  const alert = byId(page, "zombie-alert");
  await expect(alert).toBeVisible();
  await expect(alert.getByTestId("zombie-simulated")).toHaveText(en.simulated);
  await expect(alert).toContainText(demoFx.change.title);
  await expect(byId(page, "zombie-simulate")).toHaveCount(0); // once only
  // Home and results show it too (client-side navigation keeps the demo session in memory).
  await page.getByRole("link", { name: "Janus", exact: true }).click();
  await expect(byId(page, "zombie-alert")).toBeVisible();
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
  await page.getByRole("link", { name: en.openNote }).click();
  await settle(page);
  await page.getByRole("button", { name: en.update }).click();
  const changes = byId(page, "zombie-changes");
  await expect(changes).toBeVisible({ timeout: 15_000 });
  await expect(byId(page, "zombie-alert")).toHaveCount(0);
  await expect(changes.getByTestId("zombie-removed")).toHaveText(
    supportingText(DEMO_LANG),
  );
  await expect(changes).toContainText(
    `Retraction notice: ${demoFx.notice.doi}`,
  );
  await expect(byId(page, "note-paper")).not.toContainText(
    supportingText(DEMO_LANG),
  );
  await expect(byId(page, "note-paper")).toContainText(
    sentenceText(DEMO_LANG, "pipc:5:Q411347:Q388801:cascade"),
  );
  // Demo mode: no API call, nothing with a body, nothing to another origin (Req 6.1).
  const origin = new URL(page.url()).origin;
  expect(
    requests
      .filter((r) => !/^(data|blob):/.test(r.url()))
      .filter(
        (r) =>
          r.method() !== "GET" ||
          new URL(r.url()).origin !== origin ||
          new URL(r.url()).pathname.startsWith("/api/"),
      )
      .map((r) => `${r.method()} ${r.url()}`),
  ).toEqual([]);
  // Nothing written to local storage by the demo (Req 6.1).
  expect(
    await page.evaluate(() => localStorage.getItem("janus.v1.zombie")),
  ).toBeNull();
});

const items = fx.items.map(
  (
    it: {
      sourceKey: unknown;
      resolution: { dataset_version: string; candidates: unknown[] };
      started: string | null;
      boxName: string;
      choices: unknown[];
    },
    i: number,
  ) => ({
    id: `x${i}`,
    sourceKey: it.sourceKey,
    datasetVersion: it.resolution.dataset_version,
    candidate: it.resolution.candidates[0],
    choices: it.choices,
    started: it.started,
    boxName: it.boxName,
    needsConfirmation: false,
  }),
);

function withoutSupporting(note: {
  documents: {
    sections: { blocks: { id?: string; evidence_ids?: string[] }[] }[];
  }[];
}) {
  const copy = structuredClone(note);
  for (const d of copy.documents)
    for (const s of d.sections) {
      s.blocks = s.blocks.filter((b) => b.id !== SUPPORTING);
      for (const b of s.blocks)
        if (b.evidence_ids)
          b.evidence_ids = b.evidence_ids.filter((x) => x !== SOURCE);
    }
  return copy;
}

test("live: the check sends only a date; alert on home; the update shows the notice and the removed sentence", async ({
  page,
}) => {
  await page.addInitScript(
    (doc) => {
      if (!localStorage.getItem("janus.v1.list"))
        localStorage.setItem("janus.v1.list", JSON.stringify(doc));
    },
    { v: 1, items },
  );
  let notes = 0;
  const seen = await stubApi(page, {
    "/cascades/evaluate": { body: fx.evaluation },
    "/memory/snapshot": { body: fx.memory.snapshot },
    "/notes/document": () => ({
      body: ++notes === 1 ? fx.notes.en : withoutSupporting(fx.notes.en),
    }),
    "/evidence/changes": {
      body: {
        integrity_version: "new",
        as_of: "2026-11-10",
        since: "2026-11-09",
        observed_dates: ["2026-11-10"],
        status_counts: {
          ok: 3,
          corrected: 1,
          expression_of_concern: 0,
          retracted: 2,
          unknown: 0,
        },
        changes: [
          { ...demoFx.change, observed_on: "2026-11-10" },
          {
            ...demoFx.change,
            evidence_id: "paper:not_cited:x",
            observed_on: "2026-11-10",
          },
        ],
        disclaimer: "d",
      },
    },
    "/evidence/resolve": {
      body: {
        ...EVIDENCE,
        items: [
          {
            ...PAPER,
            id: SOURCE,
            title: demoFx.change.title,
            doi: demoFx.change.doi,
            integrity: {
              ...PAPER.integrity,
              status: "retracted",
              notices: [
                {
                  type: "retraction",
                  source: "crossref",
                  date: "2026-11-10",
                  notice_doi: "10.1234/example.notice",
                  notice_url: null,
                },
              ],
            },
          },
        ],
      },
    },
  });
  // The first note is made with no stored note: no check happens.
  await page.goto("/en/note");
  await settle(page);
  await page
    .getByRole("button", { name: "Make the note", exact: true })
    .click();
  await expect(byId(page, "note-paper")).toBeVisible();
  expect(seen.filter((r) => r.url().endsWith("/evidence/changes"))).toEqual([]);
  // Opening the app again checks once.
  await page.goto("/en");
  await expect(byId(page, "zombie-alert")).toBeVisible();
  await expect(byId(page, "zombie-alert")).toContainText(demoFx.change.title);
  await expect(byId(page, "zombie-alert")).not.toContainText("paper:not_cited");
  const checks = seen.filter((r) => r.url().endsWith("/evidence/changes"));
  expect(checks).toHaveLength(1);
  const body = checks[0]!.postDataJSON();
  expect(Object.keys(body).sort()).toEqual(["limit", "since"]);
  expect(body.since).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  for (const marker of [
    "paper:",
    "rule:",
    "dataset:",
    "Q",
    ...items.map((i: { boxName: string }) => i.boxName),
  ])
    expect(checks[0]!.postData()).not.toContain(marker);
  // Reloading does not alert twice or check again within the hour.
  await page.reload();
  await expect(byId(page, "zombie-alert")).toHaveCount(1);
  expect(
    seen.filter((r) => r.url().endsWith("/evidence/changes")),
  ).toHaveLength(1);
  await page.getByRole("link", { name: "Open the doctor note" }).click();
  await settle(page);
  await page.getByRole("button", { name: "Update the note" }).click();
  const changes = byId(page, "zombie-changes");
  await expect(changes).toBeVisible({ timeout: 15_000 });
  await expect(changes.getByTestId("zombie-removed")).toHaveText(
    supportingText("en"),
  );
  await expect(
    changes.getByRole("link", {
      name: "Retraction notice: 10.1234/example.notice",
    }),
  ).toHaveAttribute("href", "https://doi.org/10.1234/example.notice");
  const resolves = seen.filter((r) => r.url().endsWith("/evidence/resolve"));
  expect(resolves.map((r) => r.postDataJSON())).toEqual([
    { evidence_ids: [SOURCE] },
  ]);
  await expect(byId(page, "zombie-alert")).toHaveCount(0);
});

async function mockNotification(page: Page, answer: "granted" | "denied") {
  await page.addInitScript((a) => {
    const w = window as unknown as {
      __asked: number;
      __shown: { title: string; body: string }[];
      Notification: unknown;
    };
    w.__asked = 0;
    w.__shown = [];
    class FakeNotification {
      // Kept across page loads, like a real grant.
      static permission: string = sessionStorage.getItem("__perm") ?? "default";
      static async requestPermission() {
        w.__asked++;
        FakeNotification.permission = a;
        sessionStorage.setItem("__perm", a);
        return a;
      }
      onclick: unknown = null;
      constructor(title: string, opts: { body: string }) {
        w.__shown.push({ title, body: opts.body });
      }
    }
    w.Notification = FakeNotification;
    if (navigator.serviceWorker)
      Object.defineProperty(navigator.serviceWorker, "getRegistration", {
        value: async () => undefined,
      });
  }, answer);
}

test("notification: permission asked only after the tap; one notification without names", async ({
  page,
}) => {
  await mockNotification(page, "granted");
  await page.addInitScript(() =>
    sessionStorage.setItem("janus.v1.demo", "istanbul"),
  );
  await page.goto("/en/settings");
  const card = byId(page, "zombie-settings");
  await expect(card).toBeVisible();
  expect(
    await page.evaluate(() => (window as never as { __asked: number }).__asked),
  ).toBe(0);
  const sw = card.getByRole("switch", {
    name: messages.en.ZombieAlert.notify,
  });
  await expect(sw).not.toBeChecked();
  await sw.click();
  await expect(sw).toBeChecked();
  expect(
    await page.evaluate(() => (window as never as { __asked: number }).__asked),
  ).toBe(1);
  // The demo keeps the opt-in in memory (Req 6.1): go on by client-side navigation.
  await page
    .getByRole("link", { name: "Results", exact: true })
    .filter({ visible: true })
    .click();
  await settle(page);
  await page.getByRole("link", { name: "Prepare the doctor note" }).click();
  await settle(page);
  await page
    .getByRole("button", { name: "Make the note", exact: true })
    .click();
  await page
    .getByRole("button", { name: messages.en.ZombieAlert.simulate })
    .click();
  await expect(byId(page, "zombie-alert")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => (window as never as { __shown: { body: string }[] }).__shown,
      ),
    )
    .toEqual([
      { title: "Janus", body: messages.en.ZombieAlert.notificationDemo },
    ]);
  const shown = await page.evaluate(
    () => (window as never as { __shown: { body: string }[] }).__shown,
  );
  for (const it of items) expect(shown[0]!.body).not.toContain(it.boxName);
  expect(
    await page.evaluate(() => localStorage.getItem("janus.v1.zombie")),
  ).toBeNull();
});

test("notification: a denied permission keeps the switch off and says why", async ({
  page,
}) => {
  await mockNotification(page, "denied");
  await page.goto("/en/settings");
  const card = byId(page, "zombie-settings");
  const sw = card.getByRole("switch", {
    name: messages.en.ZombieAlert.notify,
  });
  await sw.click();
  await expect(sw).not.toBeChecked();
  await expect(card.getByRole("status")).toHaveText(
    messages.en.ZombieAlert.notifyDenied,
  );
});

for (const theme of THEMES)
  for (const locale of locales)
    test(`alert, what changed and settings, ${locale}, ${theme}`, async ({
      page,
    }) => {
      const m = messages[locale].ZombieAlert;
      await useTheme(page, theme);
      await demoNote(page, locale);
      await page.getByRole("button", { name: m.simulate }).click();
      const alert = byId(page, "zombie-alert");
      await expect(alert).toBeVisible();
      await expect(alert.getByRole("heading", { level: 2 })).toHaveText(
        m.simulatedTitle,
      );
      const text = (await alert.innerText()) ?? "";
      if (theme === "glass")
        expect(findForbiddenPhrases(text, themeWords[locale])).toEqual([]);
      await expectCardsAccessible(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      await page.getByRole("button", { name: m.update }).click();
      const changes = byId(page, "zombie-changes");
      await expect(changes).toBeVisible({ timeout: 15_000 });
      await expect(changes.getByTestId("zombie-removed")).toHaveText(
        supportingText(DEMO_LANG),
      );
      if (theme === "glass")
        expect(
          findForbiddenPhrases(await changes.innerText(), themeWords[locale]),
        ).toEqual([]);
      await expectCardsAccessible(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
      await page.goto(`/${locale}/settings`);
      await expect(byId(page, "zombie-settings")).toBeVisible();
      await expectNoAxeViolations(page);
      await expectNoHorizontalScroll(page);
      await expectTouchTargets(page);
    });

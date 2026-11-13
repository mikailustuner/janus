// Feature: medication-passport, Properties P3 (client part), P19 and the state tests (tasks
// 12.1–12.3). Validates Req 2.2, 6.1, 6.7, 9.3, 10.3–10.5, 12. The presence answer is synthetic
// (src/test/fixtures/passport.ts, generated from the request); the recorded demo files are checked in
// src/test/recorded-contract.test.ts.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { COLOGNE_PASSPORT } from "@/demo/passport-cologne";
import { routing } from "@/i18n/routing";
import { check, fc } from "@/test/fc";
import { presenceFor, presenceRecorded } from "@/test/fixtures/passport";

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    children,
    href,
    ...rest
  }: {
    children: ReactNode;
    href: unknown;
  }) => (
    <a {...rest} data-href={String(href)}>
      {children}
    </a>
  ),
  usePathname: () => "/passport",
  useRouter: () => ({ push: () => {}, replace: () => {} }),
}));

import { presenceOutArb } from "./arbitraries";
import { fromRecorded } from "./client";
import { duplicateGroups } from "./duplicates";
import { itemKeys } from "./identity";
import * as M from "./model";
import { buildPresenceRequests, fanBack } from "./request";
import { PassportItemBody } from "./screens/PassportItemView";
import { PassportListBody } from "./screens/PassportList";
import type { PresenceView } from "./screens/usePassport";
import { findPrefixWords, type Locale } from "./words";

const messages = Object.fromEntries(
  routing.locales.map((l) => [
    l,
    JSON.parse(
      readFileSync(
        join(import.meta.dirname, "../../messages", `${l}.json`),
        "utf8",
      ),
    ),
  ]),
);
const html = (
  locale: (typeof routing.locales)[number] | string,
  node: ReactNode,
) =>
  renderToStaticMarkup(
    <NextIntlClientProvider
      locale={locale as (typeof routing.locales)[number]}
      messages={messages[locale]}
      timeZone="UTC"
    >
      {node}
    </NextIntlClientProvider>,
  );
const text = (markup: string) =>
  markup
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ");

const SAME: Record<Locale, string[]> = {
  en: ["same"],
  tr: ["aynı"],
  de: ["gleich", "dieselbe", "denselben", "derselben", "dasselbe"],
  fr: ["même"],
  es: ["mismo", "misma"],
  pt: ["mesmo", "mesma"],
};

const cologneOut = presenceFor(
  buildPresenceRequests(COLOGNE_PASSPORT).bodies[0]!,
);
const okState = (
  items: readonly M.PassportItem[],
  out: M.PresenceOut,
): PresenceView => {
  const built = buildPresenceRequests(items);
  return {
    status: "ok",
    built,
    answers: fanBack(built, [out]),
    recordedOn: null,
  };
};
const body = (item: M.PassportItem, presence: PresenceView, locale = "en") =>
  html(
    locale,
    <PassportItemBody
      item={item}
      presence={presence}
      editable={false}
      retry={() => {}}
    />,
  );

const byName = (n: string) =>
  COLOGNE_PASSPORT.find((i) => i.boxName.startsWith(n))!;

describe("P3 (client): rendered rows never say 'same' when not compared", () => {
  it.each(routing.locales)("%s, generated answers", (locale) => {
    const item = byName("Ibudem");
    check(
      fc.property(presenceOutArb, (gen) => {
        const out = {
          ...gen,
          items: [{ ...gen.items[0]!, item: 0 }].filter((x) => x.answers),
        };
        if (!gen.items[0]) return;
        const markup = body(
          item,
          okState([item], out as M.PresenceOut),
          locale,
        );
        for (const m of markup.matchAll(
          /data-result="could_not_compare"[^>]*>(.*?)<\/li>/g,
        ))
          expect(
            findPrefixWords(text(m[1]!), SAME[locale as Locale]),
            m[1],
          ).toEqual([]);
      }),
      { numRuns: 40 },
    );
  });

  it("says 'as entered from the box' next to every comparison that used typed values", () => {
    let marked = 0;
    for (const item of COLOGNE_PASSPORT) {
      const markup = body(item, okState(COLOGNE_PASSPORT, cologneOut));
      const typedStrength = item.ingredients.some(
        (g) => g.strengthOrigin === "entered",
      );
      const typedForm = item.doseForm?.origin === "entered";
      for (const m of markup.matchAll(
        /<li data-result="[a-z_]+" data-field="([a-z_]+)" data-compared="(yes|no)"[^>]*>(.*?)<\/li>/g,
      )) {
        const [, field, compared, inner] = m;
        const usesTyped =
          (field !== "dose_form" && typedStrength) ||
          (field !== "strength" && typedForm);
        const row = text(inner!);
        const has = row.includes("as entered from the box");
        if (compared === "yes" && usesTyped) {
          expect(has, row).toBe(true);
          marked++;
        } else expect(has, row).toBe(false);
      }
    }
    expect(marked).toBeGreaterThanOrEqual(6);
  });
});

describe("P19 demo isolation and the recorded answer", () => {
  it("the answer is schema-valid and names its dataset and source dates", () => {
    expect(M.presenceOut(cologneOut, "$")).toBeTruthy();
    const rec = presenceRecorded(
      buildPresenceRequests(COLOGNE_PASSPORT).bodies[0]!,
    );
    expect(cologneOut.dataset_version).toBe(rec.recorded.dataset_version);
    expect(rec.recorded.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    for (const s of cologneOut.sources)
      if (s.status === "loaded")
        expect(s.snapshot_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("a recorded-shaped file answers every query the demo lists build (all three patients)", async () => {
    const { demoItems } = await import("@/demo/client");
    const { mergeLists } = await import("./merge");
    const lists: Record<string, M.PassportItem[]> = {
      cologne: COLOGNE_PASSPORT,
    };
    for (const p of ["istanbul", "ohio"]) {
      const f = (await import(`@/demo/fixtures/${p}.json`)).default;
      lists[p] = demoItems(f).map((i) => M.fromListItem(i, (_k, l) => l, true));
    }
    for (const [p, list] of Object.entries(lists)) {
      const built = buildPresenceRequests(mergeLists(list, []));
      const rec = presenceRecorded({
        items: built.bodies.flatMap((b) => b.items),
      });
      for (const b of built.bodies)
        expect(fromRecorded(rec, b), p).not.toBeNull();
    }
  });

  it("is a demo list with the cases of Req 12.1", () => {
    expect(COLOGNE_PASSPORT.every((i) => i.demo)).toBe(true);
    expect(new Set(COLOGNE_PASSPORT.map((i) => i.origin.country))).toEqual(
      new Set(["TR", "DE"]),
    );
    const dup = duplicateGroups(COLOGNE_PASSPORT);
    expect(dup.map((g) => g.key)).toEqual(["Q411347"]);
    const ids = dup[0]!.items.map((id) =>
      COLOGNE_PASSPORT.find((i) => i.id === id)!,
    );
    expect(
      ids.some((i) => i.origin.country === "TR" && itemKeys(i).length === 2),
    ).toBe(true);
    expect(ids.some((i) => i.origin.country === "DE")).toBe(true);
    expect(
      COLOGNE_PASSPORT.some((i) => i.homeopathic && i.origin.country === "DE"),
    ).toBe(true);
    expect(
      COLOGNE_PASSPORT.some((i) =>
        i.ingredients.some((g) => g.strengthOrigin === "entered"),
      ),
    ).toBe(true);
  });

  it("never puts a demo flag, name or id into a request body", () => {
    check(
      fc.property(fc.subarray(COLOGNE_PASSPORT), (list) => {
        const t = JSON.stringify(buildPresenceRequests(list).bodies);
        expect(t).not.toMatch(/demo/i);
        for (const i of list) expect(t).not.toContain(i.boxName);
      }),
    );
  });

  it("the demo client has no write or loop route", async () => {
    const { DemoClient } = await import("@/demo/client");
    const c = new DemoClient({} as never) as unknown as Record<string, unknown>;
    for (const m of [
      "contribute",
      "deleteContribution",
      "outcomes",
      "outcomeForm",
      "noteToken",
    ])
      expect(c[m]).toBeUndefined();
  });
});

describe("states (task 12.3)", () => {
  const item = byName("Ibudem");
  it("loading: busy skeleton and a polite live region", () => {
    const m = body(item, { status: "loading" });
    expect(m).toContain('aria-busy="true"');
    expect(m).toMatch(/role="status" aria-live="polite"/);
  });
  it("error: retry, never 'not found'", () => {
    const m = body(item, { status: "error", error: null });
    expect(m).toContain('role="alert"');
    expect(text(m)).toContain("These listings could not be checked now.");
    expect(text(m)).toContain("Try again");
    expect(text(m).toLowerCase()).not.toContain("not found");
  });
  it("ok: announces the loaded sources, shows the notes once, attributions, Germany", () => {
    const m = body(item, okState(COLOGNE_PASSPORT, cologneOut));
    const t = text(m);
    expect(t).toContain("Results for 4 sources loaded.");
    expect(t.split("Being listed does not mean").length - 1).toBe(1);
    expect(t).toContain("Janus shows listings in public data only.");
    expect(t).toContain("the BDPM does not endorse Janus");
    expect(t).toContain(
      "Germany has no open product database that Janus can check.",
    );
    // One grouped description list at every width (experience Req 29.3, DP56).
    expect(m).toContain("<dt");
    expect(m).toContain("<dl");
    // own source of a German box typed by name is the Germany row, shown last
    const rows = [...m.matchAll(/<dt[^>]*>(.*?)<\/dt>/g)].map((x) =>
      text(x[1]!),
    );
    expect(rows.at(-1)).toContain("Germany");
    expect(rows.at(-1)).toContain("This box's source");
  });
  it("partial: unavailable sources say why, the others render", () => {
    const out = structuredClone(cologneOut);
    out.sources[1] = {
      ...out.sources[1]!,
      status: "source_unavailable",
      reason: "not_loaded",
    };
    for (const it of out.items)
      it.answers[1] = {
        ...it.answers[1]!,
        status: "source_unavailable",
        comparison: null,
      };
    const t = text(body(item, okState(COLOGNE_PASSPORT, out)));
    expect(t).toContain("Some sources could not be checked now.");
    expect(t).toContain("This source is not available right now. Not checked.");
  });
  it("not checkable: the reason and no presence rows", () => {
    const homeo = byName("Arnidem");
    const m = body(homeo, { status: "loading" });
    expect(text(m)).toContain("Homeopathic product, not checked.");
    expect(m).not.toContain("<table");
    const partial = {
      ...item,
      ingredients: [
        ...item.ingredients,
        { ...item.ingredients[0]!, key: null, status: "unmapped" as const },
      ],
    };
    expect(text(body(partial, { status: "loading" }))).toContain(
      "Not checked: at least one ingredient of this box was not recognised.",
    );
  });
  it("statuses carry a shape, and the screens never use the risk colour", () => {
    const m = body(item, okState(COLOGNE_PASSPORT, cologneOut));
    expect(
      [...m.matchAll(/data-status="[a-z_]+"><svg/g)].length,
    ).toBeGreaterThanOrEqual(5);
    const l = html(
      "en",
      <PassportListBody items={COLOGNE_PASSPORT} demo="cologne" />,
    );
    for (const x of [m, l]) expect(x).not.toMatch(/risk/);
  });
  it("empty list: how to add a box", () => {
    const t = html("en", <PassportListBody items={[]} demo={null} />);
    expect(text(t)).toContain(
      "Your list is empty. Add a box by scanning its code or typing its name.",
    );
    expect(t).toContain('data-href="/scan"');
  });
  it("long content: 50 items with long names, never truncated", () => {
    const long = Array.from({ length: 50 }, (_, i) => ({
      ...COLOGNE_PASSPORT[i % COLOGNE_PASSPORT.length]!,
      id: `x${i}`,
      boxName: `Longnamedemoproduct${"x".repeat(80)}${i} retard filmtabletten (demo)`,
    }));
    const m = html("de", <PassportListBody items={long} demo={null} />);
    for (const i of long) expect(m).toContain(i.boxName);
    expect(m).not.toMatch(/truncate|text-ellipsis|line-clamp/);
    expect(m).toContain("[overflow-wrap:anywhere]");
  });
  it("list: duplicate chip on each box of the group, informational only", () => {
    const m = html(
      "en",
      <PassportListBody items={COLOGNE_PASSPORT} demo="cologne" />,
    );
    expect(
      text(m).split("Same active ingredient under different names:").length - 1,
    ).toBe(2);
    expect(text(m)).toContain("Both stay on your list.");
    expect(m).not.toMatch(/<button[^>]*>[^<]*(Remove|remove)/);
  });
});

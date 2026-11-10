// Feature: medication-passport, Properties P28 (wording of the product list), P29 (request
// content), P30 (rendered flags), the literal parity with the server models and the state tests
// (tasks 17.1, 18.1, 19.1). Validates Req 14.3–14.9, 15.1, 15.4, 16.1–16.5, 17.2, 17.4.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { decode } from "@/api/decode";
import { COLOGNE_PASSPORT } from "@/demo/passport-cologne";
import { COLOGNE_PRODUCTS } from "@/demo/passport-products";
import { routing } from "@/i18n/routing";
import { check, fc } from "@/test/fc";

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
  usePathname: () => "/passport/products",
  useRouter: () => ({ push: () => {}, replace: () => {} }),
}));

import { itemArb } from "./arbitraries";
import * as M from "./model";
import * as P from "./products";
import { itemQuery, notSentReason } from "./request";
import { ProductsBody } from "./screens/ProductsView";
import { findPrefixWords, substitutionWords, type Locale } from "./words";

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
const lit = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "fixtures", "schema-literals.json"),
    "utf8",
  ),
) as Record<string, unknown>;
const text = (markup: string) =>
  markup
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ");
const render = (
  item: M.PassportItem,
  state: P.ProductsState,
  locale = "en",
  target: P.Target = "eu_fr_bdpm",
) =>
  renderToStaticMarkup(
    <NextIntlClientProvider
      locale={locale as (typeof routing.locales)[number]}
      messages={messages[locale]}
      timeZone="UTC"
    >
      <ProductsBody
        item={item}
        target={target}
        onTarget={() => {}}
        state={state}
        retry={() => {}}
        more={() => {}}
      />
    </NextIntlClientProvider>,
  );

const SAME: Record<Locale, string[]> = {
  en: ["same"],
  tr: ["aynı"],
  de: ["gleich", "dieselbe", "denselben", "derselben", "dasselbe"],
  fr: ["même"],
  es: ["mismo", "misma"],
};
const byName = (n: string) =>
  COLOGNE_PASSPORT.find((i) => i.boxName.startsWith(n))!;
const amlodipine = byName("Amlodem 5");

// --- generated answers ---------------------------------------------------------------------
const NAMES = [
  "ZZ-PRODUIT 5 mg, comprimé pelliculé",
  "ZZ-Producto 10 mg COMPRIMIDOS EFG, 30 comprimidos",
  "Zz-Product",
  "ZZ-" + "Langerproduktname".repeat(12),
];
const levelArb = fc.constantFrom(...P.LEVELS);
const productArb = fc
  .record({
    name: fc.constantFrom(...NAMES),
    strength_published: fc.option(fc.constantFrom("5 mg", "10 mg/1"), {
      nil: null,
    }),
    dose_form_published: fc.option(
      fc.constantFrom("comprimé pelliculé", "TABLET"),
      { nil: null },
    ),
    dose_form_group: fc.constantFrom(...M.FORM_GROUPS.slice(0, 4)),
    strength: levelArb,
    dose_form: levelArb,
    reason: fc.constantFrom(...P.LEVEL_REASONS),
    marketed: fc.constantFrom(...P.MARKETED),
    listings: fc.integer({ min: 1, max: 40 }),
  })
  .map((r): P.ListedProduct => ({
    name: r.name,
    ingredients: [{ key: "Q411347", strength_published: r.strength_published }],
    dose_form_published: r.dose_form_published,
    dose_form_group: r.dose_form === "unknown" ? null : r.dose_form_group,
    strength: r.strength,
    strength_reason: r.strength === "unknown" ? r.reason : null,
    dose_form: r.dose_form,
    dose_form_reason: r.dose_form === "unknown" ? r.reason : null,
    marketed: r.marketed,
    listings: r.listings,
  }));
const outOf = (
  products: P.ListedProduct[],
  over: Partial<P.ProductsOut> = {},
): P.ProductsOut => {
  const tally = (f: "strength" | "dose_form") => ({
    same: products.filter((p) => p[f] === "same").length,
    different: products.filter((p) => p[f] === "different").length,
    unknown: products.filter((p) => p[f] === "unknown").length,
  });
  return {
    dataset_version: "a".repeat(64),
    form_table_version: "b".repeat(64),
    source: {
      source: 1,
      source_id: "eu_fr_bdpm",
      region: "EU",
      country: "FR",
      status: "loaded",
      reason: null,
      snapshot_date: "2026-11-03",
      stale: false,
      attribution: "bdpm",
      as_published: true,
      can_compare: { strength: true, dose_form: true },
    },
    keys: ["Q411347"],
    unknown_keys: [],
    status: products.length ? "present" : "not_present",
    total: products.length,
    listings: products.reduce((n, p) => n + p.listings, 0),
    counts: { strength: tally("strength"), dose_form: tally("dose_form") },
    with_other_ingredients: 0,
    keys_found: products.length ? ["Q411347"] : [],
    homeopathic_left_out: 0,
    not_finished_left_out: 0,
    offset: 0,
    limit: P.PAGE,
    products,
    notices: ["listing_is_lower_bound"],
    disclaimer: String(lit.disclaimer),
    ...over,
  };
};
const ok = (
  out: P.ProductsOut,
  over: Partial<Extract<P.ProductsState, { status: "ok" }>> = {},
): P.ProductsState => ({
  status: "ok",
  out,
  products: out.products,
  recordedOn: null,
  more: "idle",
  ...over,
});

describe("contract mirror (types of schemas.py)", () => {
  it("has the closed sets and limits of the server", () => {
    expect({
      listable_source_id: [...P.LISTABLE],
      level: [...P.LEVELS],
      level_reason: [...P.LEVEL_REASONS],
      marketed: [...P.MARKETED],
      listing_notice: [...P.LISTING_NOTICES],
      max_page: P.MAX_PAGE,
      max_offset: P.MAX_OFFSET,
    }).toEqual(
      Object.fromEntries(
        [
          "listable_source_id",
          "level",
          "level_reason",
          "marketed",
          "listing_notice",
          "max_page",
          "max_offset",
        ].map((k) => [k, lit[k]]),
      ),
    );
  });
  it("P25 (client): the TİTCK list and Germany are never a target", () => {
    expect(P.LISTABLE).not.toContain("titck");
    expect(Object.keys(P.TARGET_COUNTRY).sort()).toEqual(
      [...P.LISTABLE].sort(),
    );
    expect(Object.values(P.TARGET_COUNTRY)).not.toContain("TR");
    expect(Object.values(P.TARGET_COUNTRY)).not.toContain("DE");
    expect(
      P.buildProductsRequest(amlodipine, "titck" as unknown as P.Target),
    ).toBeNull();
  });
});

describe("P29 request content", () => {
  it("holds the item query, the target and the page only", () => {
    check(
      fc.property(
        itemArb(
          fc.constantFrom("Q1", "Q2", "Q3", "J1"),
          fc.constantFrom("ZZ-Secret box", "ZZ-Geheim"),
        ),
        fc.constantFrom(...P.LISTABLE),
        fc.nat(500),
        (base, target, offset) => {
          const item: M.PassportItem = { ...base, id: "zz-id-1" };
          const body = P.buildProductsRequest(item, target, offset);
          if (notSentReason(item)) {
            expect(body).toBeNull();
            return;
          }
          expect(body).toEqual({
            ...itemQuery(item),
            target,
            offset,
            limit: P.PAGE,
          });
          const allowed = new Set([
            "ingredients",
            "dose_form",
            "target",
            "offset",
            "limit",
          ]);
          expect(Object.keys(body!).every((k) => allowed.has(k))).toBe(true);
          for (const g of body!.ingredients)
            expect(
              Object.keys(g).every((k) => k === "key" || k === "strength"),
            ).toBe(true);
          const sent = JSON.stringify(body);
          for (const secret of ["ZZ-", "zz-id", "scan", "2024", "titck"])
            expect(sent).not.toContain(secret);
        },
      ),
    );
  });
});

describe.each(routing.locales)("P28 wording, %s", (locale) => {
  const l = locale as Locale;
  const tree = messages[locale].Passport.products;
  const en = messages.en.Passport.products;
  const args = (s: string) =>
    [...s.matchAll(/\{\s*([A-Za-z_]\w*)\s*(?:\}|,\s*(?:plural|select))/g)]
      .map((m) => m[1])
      .sort();
  const get = (t: unknown, path: string) =>
    path.split(".").reduce<unknown>((o, p) => (o as never)?.[p], t) as string;

  it("every level, marketing code, notice and target has a key with the English parameters", () => {
    const need = [
      ...["strength", "dose_form"].flatMap((f) =>
        P.LEVELS.map((v) => `${f}.${v}`),
      ),
      ...["strength", "dose_form"].map((f) => `counts.${f}`),
      ...P.MARKETED.map((m) => `marketed.${m}`),
      ...P.LISTING_NOTICES.map((n) => `notice.${n}`),
      "caution.title",
      "caution.notSame",
      "caution.confirm",
      "caution.noDosing",
      "notes.automated",
      "notes.salt",
      "notes.order",
      "notes.group",
      "notListed",
      "flag",
      "open",
    ];
    for (const key of need) {
      expect(get(tree, key), key).toBeTruthy();
      expect(args(get(tree, key)), key).toEqual(args(get(en, key)));
    }
    for (const t of P.LISTABLE)
      expect(messages[locale].Passport.place[P.TARGET_COUNTRY[t]]).toBeTruthy();
    for (const r of P.LEVEL_REASONS)
      expect(messages[locale].Passport.compareReason[r]).toBeTruthy();
  });

  it("'different' and 'not compared' never say 'same'", () => {
    for (const f of ["strength", "dose_form"])
      for (const v of ["different", "unknown"])
        expect(
          findPrefixWords(get(tree, `${f}.${v}`), SAME[l]),
          `${f}.${v}`,
        ).toEqual([]);
    expect(findPrefixWords(tree.flag, SAME[l])).toEqual([]);
  });

  it("P30: rows are flagged exactly by their level and carry no substitution word", () => {
    check(
      fc.property(fc.array(productArb, { maxLength: 6 }), (products) => {
        const m = render(amlodipine, ok(outOf(products)), locale);
        const rows = m.split('data-testid="listed-product"').slice(1);
        expect(rows.length).toBe(products.length);
        const sameStrength = tree.strength.same as string;
        products.forEach((p, i) => {
          const row = rows[i]!.split("</li>")[0]!;
          const flags = row.split('data-testid="different"').length - 1;
          expect(flags).toBe(
            Number(p.strength === "different") +
              Number(p.dose_form === "different"),
          );
          expect(text(row).includes(sameStrength)).toBe(p.strength === "same");
          expect(row).toContain(
            `data-field="strength" data-level="${p.strength}"`,
          );
          expect(row).toContain(
            `data-field="dose_form" data-level="${p.dose_form}"`,
          );
        });
        expect(findPrefixWords(text(m), substitutionWords[l])).toEqual([]);
        expect(m).toContain('data-testid="products-caution"');
        expect(text(m)).toContain(tree.caution.confirm);
        expect(text(m)).toContain(tree.caution.noDosing);
        // Req 16.3: the salt and base note sits with the counts, above the rows, once.
        expect(text(m).split(tree.notes.salt).length - 1).toBe(1);
        expect(m.includes('data-testid="salt-note"')).toBe(products.length > 0);
        expect(m).not.toMatch(/text-risk|bg-risk|border-risk/);
      }),
      { numRuns: 60 },
    );
  });
});

describe("wording rules (Req 16)", () => {
  const en = messages.en.Passport.products;
  it("says 'contains the same active ingredient' and never 'the same medicine' as a claim", () => {
    expect(en.caution.notSame).toContain("contains");
    expect(en.caution.notSame).toContain("same active ingredient");
    expect(en.caution.notSame).toContain(
      "That does not make it the same medicine",
    );
    expect(en.caution.confirm).toBe(
      "Confirm with a pharmacist or doctor before you take a different product.",
    );
  });
  it("describes the comparison as automated and states the review status", () => {
    expect(en.notes.automated).toContain("automated");
    expect(en.notes.automated).toContain(
      "Expert review has not yet been done.",
    );
    for (const l of routing.locales)
      expect(JSON.stringify(messages[l].Passport.products)).not.toMatch(
        /\bAI\b|\bKI\b|\bIA\b|yapay zek|reviewed by|geprüft von/i,
      );
  });
});

describe("states (Req 17.2, 17.4)", () => {
  it("loading: busy skeleton, the caution text and a polite live region", () => {
    const m = render(amlodipine, { status: "loading" });
    expect(m).toContain('aria-busy="true"');
    expect(m).toMatch(/role="status" aria-live="polite"/);
    expect(m).toContain('data-testid="products-caution"');
    expect(text(m)).toContain("Looking up the products…");
  });
  it("error: retry, never 'not found'", () => {
    const m = render(amlodipine, { status: "error", error: null });
    expect(m).toContain('role="alert"');
    expect(text(m)).toContain("The products could not be looked up now.");
    expect(text(m)).toContain("Try again");
    expect(text(m).toLowerCase()).not.toContain("not found");
  });
  it("nothing listed: a statement about the source data, never 'not available'", () => {
    const m = text(
      render(
        amlodipine,
        ok(outOf([], { with_other_ingredients: 12, status: "not_present" })),
      ),
    );
    expect(m).toContain("BDPM lists no product with this active ingredient");
    expect(m).toContain("12 products contain this active ingredient together");
    expect(m).toContain("Source: Base de données publique des médicaments");
    expect(m.toLowerCase()).not.toContain("not available");
    expect(m).not.toContain("Show more");
  });
  it("source unavailable: says so and lists nothing", () => {
    const out = outOf([], { status: "source_unavailable" });
    out.source = {
      ...out.source,
      status: "source_unavailable",
      reason: "not_loaded",
      snapshot_date: null,
    };
    const m = render(amlodipine, ok(out));
    expect(text(m)).toContain("This source is not available right now.");
    expect(m).not.toContain('data-testid="listed-product"');
  });
  it("not checkable: the reason, no country choice and no list", () => {
    const m = render(byName("Arnidem"), { status: "loading" });
    expect(text(m)).toContain("Homeopathic product, not checked.");
    expect(m).not.toContain('type="radio"');
    expect(m).not.toContain('aria-busy="true"');
  });
  it("demo without a recorded answer says the list is not part of the demo", () => {
    expect(text(render(amlodipine, { status: "not_in_demo" }))).toContain(
      "The product list is not part of this demo patient.",
    );
  });
  it("long list: 50 rows with long names, the shown and total numbers, Show more", () => {
    const row: P.ListedProduct = {
      name: NAMES[3]!,
      ingredients: [{ key: "Q411347", strength_published: "10 mg" }],
      dose_form_published: "comprimé pelliculé",
      dose_form_group: "oral_solid",
      strength: "different",
      strength_reason: null,
      dose_form: "same",
      dose_form_reason: null,
      marketed: "listed_as_not_marketed",
      listings: 3,
    };
    const products = Array.from({ length: 50 }, () => row);
    const m = render(amlodipine, ok(outOf(products, { total: 137 })));
    expect(m.split('data-testid="listed-product"').length - 1).toBe(50);
    expect(m.split(NAMES[3]!).length - 1).toBe(50);
    expect(m).toContain("[overflow-wrap:anywhere]");
    const t = text(m);
    expect(t).toContain("Showing 50 of 137 rows.");
    expect(t).toContain("Show more");
    expect(t).toContain("Different listed strength:");
    expect(t).toContain("Listed as not marketed in the source data.");
    expect(t).toContain("3 entries in the source with this name");
    expect(m).toContain('lang="fr"');
  });
  it("the country choice is a labelled radio group of the listable countries", () => {
    const m = render(amlodipine, { status: "loading" });
    expect(m.split('type="radio"').length - 1).toBe(P.LISTABLE.length);
    expect(text(m)).toContain("Country to look in");
    expect(text(m)).toContain("Product names from Türkiye are not shown");
    expect(text(m)).toContain("Germany has no open product database.");
  });
});

describe("recorded demo answers (DP33)", () => {
  it("are schema-valid, from listable sources only, with exactly the query's keys", () => {
    expect(COLOGNE_PRODUCTS.recorded.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    for (const a of COLOGNE_PRODUCTS.answers) {
      const d = decode(P.productsOut, a.response);
      expect(d.ok).toBe(true);
      if (!d.ok) continue;
      expect(P.LISTABLE).toContain(d.value.source.source_id);
      expect(d.value.source.source_id).toBe(a.request.target);
      expect(d.value.source.snapshot_date).toBeTruthy();
      expect(d.value.dataset_version).toBe(
        COLOGNE_PRODUCTS.recorded.dataset_version,
      );
      const keys = a.request.ingredients.map((g) => g.key).sort();
      for (const p of d.value.products) {
        expect([...new Set(p.ingredients.map((g) => g.key))].sort()).toEqual(
          keys,
        );
        // P23 on real data: no "same" without a strength on the box.
        if (a.request.ingredients.some((g) => !g.strength))
          expect(p.strength).toBe("unknown");
        if (!a.request.dose_form) expect(p.dose_form).toBe("unknown");
      }
    }
  });
  it("hold every query the Cologne list builds, for every target", async () => {
    for (const item of COLOGNE_PASSPORT)
      for (const target of P.LISTABLE) {
        const body = P.buildProductsRequest(item, target);
        if (!body) continue;
        const state = await P.loadProducts(body, null, COLOGNE_PRODUCTS);
        expect(state.status, `${item.boxName} ${target}`).toBe("ok");
      }
    const body = P.buildProductsRequest(amlodipine, "eu_fr_bdpm")!;
    expect((await P.loadProducts(body, null, null)).status).toBe("not_in_demo");
  });
  it("render with the recorded date and without a call for more", async () => {
    const body = P.buildProductsRequest(amlodipine, "eu_fr_bdpm")!;
    const state = await P.loadProducts(body, null, COLOGNE_PRODUCTS);
    const t = text(render(amlodipine, state));
    expect(t).toMatch(/Recorded answer of \d{4}-\d{2}-\d{2}\./);
    expect(t).toContain("The demo holds the first");
    expect(t).not.toContain("Show more");
    expect(t).toContain("Same listed strength:");
    expect(t).toContain("the BDPM does not endorse Janus");
  });
});

describe("paging", () => {
  const page = (n: number, offset: number): P.ProductsOut =>
    outOf(
      Array.from({ length: n }, (_, i) => ({
        name: `ZZ-${offset + i}`,
        ingredients: [{ key: "Q411347", strength_published: "5 mg" }],
        dose_form_published: null,
        dose_form_group: null,
        strength: "unknown" as const,
        strength_reason: "not_known_for_item" as const,
        dose_form: "unknown" as const,
        dose_form_reason: "not_known_for_item" as const,
        marketed: "not_stated" as const,
        listings: 1,
      })),
      { total: 70, offset },
    );
  const body = P.buildProductsRequest(amlodipine, "openfda_ndc")!;
  it("appends the next page from the number of rows already shown", async () => {
    const offsets: number[] = [];
    const call: P.ProductsCall = async (b) => {
      offsets.push(b.offset);
      return { ok: true, data: page(b.offset === 0 ? 50 : 20, b.offset) };
    };
    const first = await P.loadProducts(body, call);
    expect(first.status).toBe("ok");
    if (first.status !== "ok") return;
    const next = await P.loadMore(first, body, call);
    expect(offsets).toEqual([0, 50]);
    expect(next.products.map((p) => p.name)).toEqual(
      Array.from({ length: 70 }, (_, i) => `ZZ-${i}`),
    );
    expect(next.more).toBe("idle");
  });
  it("keeps the rows when the next page fails or comes from another dataset", async () => {
    const first = await P.loadProducts(body, async () => ({
      ok: true,
      data: page(50, 0),
    }));
    if (first.status !== "ok") throw new Error("first page");
    const other = await P.loadMore(first, body, async () => ({
      ok: true,
      data: { ...page(20, 50), dataset_version: "c".repeat(64) },
    }));
    expect([other.more, other.products.length]).toEqual(["error", 50]);
    const failed = await P.loadMore(first, body, async () => ({
      ok: false,
      error: {
        kind: "network",
        route: "passport/products",
        messageKey: "Errors.network",
      },
    }));
    expect([failed.more, failed.products.length]).toEqual(["error", 50]);
    expect(text(render(amlodipine, failed))).toContain(
      "More products could not be loaded now.",
    );
  });
});

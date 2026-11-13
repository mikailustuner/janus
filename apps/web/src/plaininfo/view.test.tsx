// Feature: plain-medicine-info, web properties W4–W6 (design §7). Validates Req 1.2, 1.3, 5.2–5.7:
// a group sentence is rendered only from the answer and always with the review line; the official
// text is a quotation in its own language, unchanged; "no information" is never a statement about
// the medicine; red only in the emergency notice.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { Locale } from "@/api/contracts";
import { decode } from "@/api/decode";
import { MedicineInfoBody } from "@/components/plaininfo/MedicineInfo";
import { violations } from "@/test/plaininfo-words";
import { demoItems, type Fixture } from "@/demo/client";
import istanbul from "@/demo/fixtures/istanbul.json";
import { routing } from "@/i18n/routing";
import type { Loaded, Vocabulary, VocabularyIndex } from "@/vocabulary";
import index from "@/vocabulary/index.json";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={String(href)}>{children}</a>
  ),
}));

import {
  medicineInfoOut,
  type MedicineInfoIn,
  type MedicineInfoOut,
} from "./model";
import type { InfoQuery } from "./query";
import { infoQuery } from "./query";
import type { InfoState } from "./useMedicineInfo";

type Tree = { [key: string]: string | Tree };
const read = (path: string) =>
  JSON.parse(readFileSync(join(import.meta.dirname, path), "utf8"));
const LOCALES = routing.locales as readonly Locale[];
const catalogues = Object.fromEntries(
  LOCALES.map((l) => [l, read(`../../messages/${l}.json`) as Tree]),
) as Record<Locale, Tree>;
const vocabs = Object.fromEntries(
  LOCALES.map((l) => [
    l,
    {
      locale: l,
      vocab: read(`../vocabulary/${l}.json`) as Vocabulary,
      index: index as VocabularyIndex,
    } satisfies Loaded,
  ]),
) as Record<Locale, Loaded>;
const plain = (l: Locale) => catalogues[l].PlainInfo as Tree;
const leaf = (l: Locale, path: string) =>
  path
    .split(".")
    .reduce<string | Tree>((t, k) => (t as Tree)[k]!, plain(l)) as string;

const raw = read("fixtures/info.json") as Record<string, unknown>;
const answer = (name: string): MedicineInfoOut => {
  const r = decode(medicineInfoOut, raw[name]);
  if (!r.ok) throw new Error(`${name}: ${r.path}`);
  return r.value;
};
const ok = (data: MedicineInfoOut): InfoState => ({ status: "ok", data });

const items = demoItems(istanbul as unknown as Fixture);
// A query with as many asked ingredients as the answer has, built from real list items.
function queryFor(
  l: Locale,
  data: MedicineInfoOut,
  product: NonNullable<MedicineInfoIn["product"]> | undefined,
  noProduct: InfoQuery["noProduct"] = null,
): InfoQuery {
  const item = items.find(
    (i) =>
      infoQuery(vocabs[l], i, l, true).body?.ingredients.length ===
      data.ingredients.length,
  )!;
  const q = infoQuery(vocabs[l], item, l, true);
  return {
    ...q,
    noProduct,
    body: { ...q.body!, ...(product ? { product } : {}) },
  };
}

const html = (l: Locale, node: ReactNode) =>
  renderToStaticMarkup(
    <NextIntlClientProvider
      locale={l}
      messages={catalogues[l] as never}
      timeZone="UTC"
    >
      {node}
    </NextIntlClientProvider>,
  );
const unescape = (s: string) =>
  s
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
const text = (markup: string) =>
  unescape(
    markup
      .replace(/<blockquote[\s\S]*?<\/blockquote>/g, " ") // the label's words, quoted in English
      .replace(/<[^>]+>/g, " "),
  ).replace(/\s+/g, " ");
const count = (markup: string, testid: string) =>
  markup.split(`data-testid="${testid}"`).length - 1;
const body = (
  l: Locale,
  query: InfoQuery,
  state: InfoState | { status: "nothing" },
) =>
  html(
    l,
    <MedicineInfoBody
      boxName="Kutu <1> (invented)"
      query={query}
      state={state}
      vocab={vocabs[l]}
    />,
  );

describe.each(LOCALES)("MedicineInfo, %s", (l) => {
  const us = answer("us");
  const fr = answer("fr");
  const long = answer("long");
  const none = answer("none");
  const usQuery = queryFor(l, us, { country: "US", ndc: "99999-0123" });
  const usMarkup = body(l, usQuery, ok(us));

  it("W4: shows every group sentence of the answer, each with the review line", () => {
    const groups = us.ingredients.flatMap((i) => i.groups);
    expect(groups.length).toBeGreaterThan(0);
    const out = text(usMarkup);
    for (const g of groups) {
      expect(out).toContain(g.name);
      expect(out).toContain(g.text);
      expect(out).toContain(g.codes.join(", "));
    }
    expect(count(usMarkup, "plain-info-sentence")).toBe(groups.length);
    expect(count(usMarkup, "plain-info-review")).toBe(groups.length);
    expect(out).toContain(leaf(l, "review"));
    expect(out).toContain(leaf(l, "method"));
    expect(out).toContain(leaf(l, "limits.group"));
    expect(out).toContain(leaf(l, "limits.dose"));
    expect(out).toContain(leaf(l, "limits.ask"));
  });

  it("W4: quotes the official text unchanged, in English, marked as not translated", () => {
    if (us.official?.kind !== "label_text") throw new Error("fixture");
    const quote =
      /<blockquote lang="en" dir="ltr"[^>]*>([\s\S]*?)<\/blockquote>/.exec(
        usMarkup,
      )![1]!;
    const paragraphs = [...quote.matchAll(/<p>([\s\S]*?)<\/p>/g)].map((m) =>
      unescape(m[1]!),
    );
    expect(paragraphs).toEqual(us.official.paragraphs);
    const out = text(usMarkup);
    expect(out).toContain(leaf(l, "official.us.language"));
    expect(out).toContain(leaf(l, "official.us.company"));
    expect(out).toContain(leaf(l, "official.us.differ"));
    expect(out).not.toContain(leaf(l, "official.us.cut"));
    expect(usMarkup).toContain(`href="${us.official.url}"`);
    // The label's words appear nowhere outside the quotation.
    expect(out).not.toContain("Exampletine");
  });

  it("W4: a cut text says so and links to the full label", () => {
    const markup = body(
      l,
      queryFor(l, long, { country: "US", ndc: "99999-0777" }),
      ok(long),
    );
    expect(text(markup)).toContain(leaf(l, "official.us.cut"));
    expect(text(markup)).toContain(leaf(l, "group.mixed"));
    expect(text(markup)).not.toContain(leaf(l, "group.otherUses"));
  });

  it("links to the product page with its language and the name check", () => {
    if (fr.official?.kind !== "product_page") throw new Error("fixture");
    const markup = body(
      l,
      queryFor(l, fr, { country: "FR", name: "EXEMPLINE (inventé)" }),
      ok(fr),
    );
    const out = text(markup);
    expect(markup).toContain(`href="${fr.official.url}"`);
    expect(out).toContain(leaf(l, "official.page.title.FR"));
    expect(out).toContain(leaf(l, "official.page.language.fr"));
    expect(out).toContain(leaf(l, "group.mixed"));
    expect(out).toContain(leaf(l, "group.otherUses"));
    expect(markup).not.toContain("<blockquote");
  });

  it("W5: says clearly when there is no information, and only then", () => {
    const noneMarkup = body(
      l,
      queryFor(l, none, undefined, "country"),
      ok(none),
    );
    const out = text(noneMarkup);
    expect(count(noneMarkup, "plain-info-nothing")).toBe(1);
    expect(out).toContain(leaf(l, "nothing.title"));
    expect(out).toContain(leaf(l, "nothing.body"));
    expect(out).toContain(leaf(l, "group.none"));
    expect(out).toContain(leaf(l, "official.none.country"));
    expect(out).toContain(leaf(l, "limits.ask"));
    expect(count(noneMarkup, "plain-info-sentence")).toBe(0);
    expect(count(noneMarkup, "plain-info-review")).toBe(0);
    expect(out).not.toContain(leaf(l, "method"));
    expect(count(usMarkup, "plain-info-nothing")).toBe(0);
    // Nothing asked at all (every ingredient unchecked, no product) is the same state.
    const nothing = body(
      l,
      {
        ...usQuery,
        asked: usQuery.asked.map(() => null),
        body: null,
        noProduct: "country",
      },
      { status: "nothing" },
    );
    expect(count(nothing, "plain-info-nothing")).toBe(1);
  });

  it("W6: the abrupt-stop line appears exactly for flagged ingredients; red only in the emergency notice", () => {
    const flagged = us.ingredients.filter((i) => i.abrupt_stop).length;
    expect(flagged).toBe(1);
    expect(count(usMarkup, "abrupt-stop")).toBe(flagged);
    for (const markup of [
      usMarkup,
      body(l, queryFor(l, none, undefined, "demo"), ok(none)),
    ]) {
      const outside = markup.replace(
        /<aside[^>]*data-testid="emergency-notice"[\s\S]*?<\/aside>/,
        "",
      );
      expect(outside).not.toMatch(/\brisk\b/);
      expect(markup.indexOf('data-testid="emergency-notice"')).toBeLessThan(
        markup.indexOf("<h1"),
      );
    }
  });

  it("has no forbidden, reassurance or 'AI' word in any rendering", () => {
    const renderings = [
      usMarkup,
      body(l, queryFor(l, fr, { country: "FR", name: "x" }), ok(fr)),
      body(l, queryFor(l, none, undefined, "demo"), ok(none)),
      body(l, queryFor(l, none, undefined, "homeopathic"), ok(none)),
      body(l, queryFor(l, none, undefined, "by_name"), ok(none)),
      body(l, queryFor(l, none, undefined, "no_code"), ok(none)),
      body(
        l,
        queryFor(l, none, { country: "US", ndc: "1-1" }),
        ok({ ...none, official_status: "not_found" }),
      ),
      body(
        l,
        queryFor(l, none, { country: "ES", name: "x" }),
        ok({ ...none, official_status: "not_found" }),
      ),
      body(
        l,
        queryFor(l, none, { country: "US", ndc: "1-1" }),
        ok({ ...none, official_status: "several_labels" }),
      ),
      body(
        l,
        queryFor(l, none, { country: "US", ndc: "1-1" }),
        ok({ ...none, official_status: "source_unavailable" }),
      ),
      body(
        l,
        usQuery,
        ok({ ...us, notices: [...us.notices, "snapshot_outdated"] }),
      ),
    ];
    for (const markup of renderings)
      expect(violations(text(markup), l)).toEqual([]);
    expect(text(renderings[10]!)).toContain(leaf(l, "official.us.outdated"));
    expect(text(renderings[8]!)).toContain(
      leaf(l, "official.none.several_labels"),
    );
    expect(text(renderings[6]!)).toContain(
      leaf(l, "official.none.not_found_us"),
    );
    expect(text(renderings[7]!)).toContain(
      leaf(l, "official.none.not_found_page"),
    );
  });

  it("shows loading and error states without any medical content", () => {
    const loading = body(l, usQuery, { status: "loading" });
    expect(loading).toContain('aria-busy="true"');
    expect(text(loading)).toContain(leaf(l, "loading"));
    const error = body(l, usQuery, {
      status: "error",
      error: {
        kind: "http",
        route: "medicine-info",
        status: 503,
        code: "medicine_info_unavailable",
        fields: [],
        messageKey: "PlainInfo.errors.unavailable",
      },
    });
    expect(error).toContain('role="alert"');
    expect(text(error)).toContain(leaf(l, "errors.unavailable"));
    for (const markup of [loading, error]) {
      expect(count(markup, "plain-info-ingredient")).toBe(0);
      expect(count(markup, "plain-info-nothing")).toBe(0);
      expect(text(markup)).toContain("Kutu <1> (invented)"); // the box name, escaped
    }
  });
});

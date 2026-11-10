// Feature: recall-check, web properties W5–W7 (design §8). Validates Req 6.2–6.6, 6.8, 6.9, 8.3:
// the notice in five languages quotes the record and its limits; nothing found is never a
// statement that the medicine is fine; no forbidden or reassurance word; no red.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { NextIntlClientProvider, createTranslator } from "next-intl";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { decode } from "@/api/decode";
import { RecallView } from "@/components/recall/RecallCheck";
import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "@/i18n/forbidden-phrases";
import { reassurance } from "@/i18n/reassurance";
import { routing } from "@/i18n/routing";
import { check, fc } from "@/test/fc";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children }: { children: ReactNode }) => <a>{children}</a>,
}));

import { recallCheckOut, type RecallCheckOut } from "./model";
import type { RecallState } from "./useRecall";

type Locale = (typeof routing.locales)[number];
type Tree = { [key: string]: string | Tree };
const read = (path: string) =>
  JSON.parse(readFileSync(join(import.meta.dirname, path), "utf8"));
const catalogues = Object.fromEntries(
  routing.locales.map((l) => [l, read(`../../messages/${l}.json`) as Tree]),
) as Record<Locale, Tree>;

function flatten(tree: Tree, prefix = ""): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out.set(path, value);
    else for (const [k, v] of flatten(value, path)) out.set(k, v);
  }
  return out;
}
const recall = (l: Locale) =>
  new Map([...flatten(catalogues[l])].filter(([k]) => k.startsWith("Recall.")));
const args = (message: string) =>
  [...message.matchAll(/\{\s*([A-Za-z_]\w*)\s*(?:\}|,)/g)]
    .map((m) => m[1]!)
    .sort();

const decoded = decode(recallCheckOut, read("fixtures/check.json"));
if (!decoded.ok) throw new Error("fixture does not match the contract");
const sample: RecallCheckOut = decoded.value;
const ok = (data: RecallCheckOut): RecallState => ({ status: "ok", data });
const none = ok({ ...sample, matches: [], total_matches: 0 });

const html = (locale: Locale, node: ReactNode) =>
  renderToStaticMarkup(
    <NextIntlClientProvider
      locale={locale}
      messages={catalogues[locale] as never}
      timeZone="UTC"
    >
      {node}
    </NextIntlClientProvider>,
  );
const text = (markup: string) =>
  markup
    .replace(/<blockquote[\s\S]*?<\/blockquote>/g, " ") // FDA's words, quoted in English
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ");

/** Words a recall text must never use: forbidden phrases, reassurance, and "AI" for the method. */
const AI: Record<Locale, string[]> = {
  en: ["AI", "artificial intelligence"],
  tr: ["yapay zeka", "yapay zekâ"],
  de: ["KI", "künstliche Intelligenz"],
  fr: ["IA", "intelligence artificielle"],
  es: ["IA", "inteligencia artificial"],
};
const violations = (value: string, l: Locale) => [
  ...findForbiddenPhrases(value, forbiddenPhrases[l]),
  ...findForbiddenPhrases(value, reassurance[l]),
  ...AI[l].filter((w) =>
    new RegExp(`(?<!\\p{L})${w}(?!\\p{L})`, "u").test(value),
  ),
];

describe.each(routing.locales)("Recall texts, %s", (locale) => {
  const l = locale as Locale;
  const messages = recall(l);
  const en = recall("en");
  const t = createTranslator({ locale, messages: catalogues[l] as never });

  it("W5: every key of English, with the same parameters", () => {
    expect([...messages.keys()].sort()).toEqual([...en.keys()].sort());
    expect(messages.size).toBeGreaterThanOrEqual(38);
    for (const [key, value] of messages)
      expect(args(value), key).toEqual(args(en.get(key)!));
  });

  it("W5: no forbidden, reassurance or 'AI' word in any text or rendering", () => {
    for (const [key, value] of messages)
      expect(violations(value, l), key).toEqual([]);
    check(
      fc.property(
        fc.constantFrom(...messages.keys()),
        fc.integer({ min: 0, max: 30 }),
        fc.constantFrom("ZZ-12", "3 Nov 2026", "Ongoing"),
        (key, n, word) => {
          const values: Record<string, string | number> = {};
          for (const name of args(messages.get(key)!))
            values[name] = ["count", "without", "records"].includes(name)
              ? n
              : word;
          const out = t(key as never, values as never) as string;
          expect(violations(out, l), `${key}: ${out}`).toEqual([]);
        },
      ),
    );
  });

  it("W6: nothing found names the data date and the US, and is not a clearance", () => {
    const out = text(html(l, <RecallView state={none} lot="AB1234" />));
    expect(out).toContain(
      t("Recall.none" as never, { date: "X" } as never)
        .split("X")[0]!
        .trim(),
    );
    expect(out).toMatch(/2026/);
    expect(out).toContain(t("Common.region.US" as never));
    expect(out).toContain(t("Recall.about" as never));
    expect(violations(out, l)).toEqual([]);
    expect(out).not.toContain("AB1234"); // no lot is echoed when nothing matched
  });

  it("W7: a notice shows the record, the lot line, the advice and both links", () => {
    for (const lot of ["ab-1234", "ZZ9", null]) {
      const markup = html(l, <RecallView state={ok(sample)} lot={lot} />);
      const out = text(markup);
      expect(markup.match(/data-testid="recall-notice"/g)).toHaveLength(3);
      for (const m of sample.matches) {
        expect(markup).toContain(m.recall_number);
        expect(markup).toContain(m.record_url.replace(/&/g, "&amp;"));
        expect(markup).toContain(m.reason_for_recall!);
      }
      expect(markup).toContain(`href="${sample.source.search_url}"`);
      expect(out).toContain(t("Recall.advice" as never));
      expect(out).toContain(t("Recall.statusValue.Ongoing" as never));
      // A terminated recall is labelled, with its date; never shown as ongoing.
      expect(markup).toMatch(
        /data-testid="recall-status">[^<]*2025[^<]*<\/dd>/,
      );
      expect(out).toContain(
        t("Recall.terminatedOn" as never, { date: "X" } as never)
          .replace("X", "")
          .trim()
          .split(" ")[0]!,
      );
      const listed = (markup.match(/data-lot="listed"/g) ?? []).length;
      expect(listed).toBe(lot === "ab-1234" ? 1 : 0);
      expect(out.includes(t("Recall.title.lot" as never))).toBe(listed === 1);
      expect(out).toContain(t("Recall.title.product" as never));
      if (lot === "ZZ9")
        expect(out).toContain(
          t("Recall.lot.not_listed" as never, { lot } as never),
        );
      if (lot === null)
        expect(out).toContain(t("Recall.lot.not_given" as never));
      expect(out).toContain(t("Recall.lotTextCut" as never));
      expect(violations(out, l)).toEqual([]);
      // Quotes are marked as English; red is never used (design.md shared rules).
      expect(markup).toContain('<blockquote lang="en"');
      expect(markup).not.toMatch(/text-risk|border-risk|bg-risk/);
      expect(markup).toMatch(/rel="noopener noreferrer"/);
    }
  });

  it("W7: loading, error with retry, hidden records and outdated data", () => {
    const loading = html(
      l,
      <RecallView state={{ status: "loading" }} lot={null} />,
    );
    expect(loading).toContain('role="status"');
    expect(loading).toContain('aria-busy="true"');
    const failed = html(
      l,
      <RecallView
        state={{
          status: "error",
          error: {
            kind: "http",
            route: "recalls/check",
            status: 503,
            code: "recalls_unavailable",
            fields: [],
            messageKey: "Recall.errors.unavailable",
          },
        }}
        lot={null}
        retry={() => {}}
      />,
    );
    expect(failed).toContain('role="alert"');
    expect(text(failed)).toContain(t("Recall.errors.unavailable" as never));
    expect(text(failed)).toContain(t("Common.retry" as never));
    const more = text(
      html(
        l,
        <RecallView
          state={ok({
            ...sample,
            total_matches: 25,
            truncated: true,
            notices: [...sample.notices, "snapshot_outdated"],
          })}
          lot={null}
        />,
      ),
    );
    expect(more).toContain(t("Recall.more" as never, { count: 22 } as never));
    expect(more).toContain(t("Recall.outdated" as never));
  });
});

it("the English reference texts of Req 6 are kept", () => {
  const en = recall("en");
  expect(en.get("Recall.title.product")).toBe(
    "This product appears in an FDA recall record",
  );
  expect(en.get("Recall.title.lot")).toBe(
    "This product and lot appear in an FDA recall record",
  );
  expect(en.get("Recall.none")).toBe(
    "FDA recall records up to {date} (United States only) were checked: no record names this product code. This does not mean this medicine is free of problems.",
  );
  expect(en.get("Recall.method")).toContain(
    "Expert review has not yet been done.",
  );
  expect(en.get("Recall.method")).toContain("Automated lookup");
  expect(en.get("Recall.advice")).toContain("A pharmacist can check it");
});

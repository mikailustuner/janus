// Feature: janus-report, Properties P2, P4, P8 (design §6): the rendered Summary shows the
// abrupt-stop line once per warned item; with no finding it shows the no-pattern sentence and no
// large zero; the emergency notice comes first iff a safety line applies; no forbidden phrase or
// reassurance word in any locale, and no theme-device word in Glass Janus.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { NextIntlClientProvider } from "next-intl";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "@/i18n/forbidden-phrases";
import { reassurance, themeWords } from "@/i18n/reassurance";
import { routing } from "@/i18n/routing";
import { check, fc } from "@/test/fc";
import { EVIDENCE } from "@/test/results";
import { summaryInputArb } from "@/test/summary";
import { ThemeOverride } from "@/theme/words";
import type { Loaded, Vocabulary, VocabularyIndex } from "@/vocabulary";
import index from "@/vocabulary/index.json";
import { integritySummary, summaryView } from "@/flow/summary";

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: unknown;
  }) => (
    <a {...rest} data-href={JSON.stringify(href)}>
      {children}
    </a>
  ),
  usePathname: () => "/results/summary",
  useRouter: () => ({ push: () => {}, replace: () => {} }),
}));

import { SummaryBody, type IntegrityState } from "./Summary";

type Locale = (typeof routing.locales)[number];
const messages = Object.fromEntries(
  routing.locales.map((l) => [
    l,
    JSON.parse(
      readFileSync(
        join(import.meta.dirname, "../../../messages", `${l}.json`),
        "utf8",
      ),
    ),
  ]),
);
const vocabs = Object.fromEntries(
  routing.locales.map((l) => [
    l,
    {
      locale: l,
      vocab: JSON.parse(
        readFileSync(
          join(import.meta.dirname, "../../vocabulary", `${l}.json`),
          "utf8",
        ),
      ) as Vocabulary,
      index: index as unknown as VocabularyIndex,
    } satisfies Loaded,
  ]),
) as Record<Locale, Loaded>;

function html(
  locale: Locale,
  theme: "two-faces" | "glass",
  node: React.ReactNode,
) {
  return renderToStaticMarkup(
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      <ThemeOverride.Provider value={theme}>{node}</ThemeOverride.Provider>
    </NextIntlClientProvider>,
  );
}
const text = (h: string) =>
  h
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&");

const integrityArb: fc.Arbitrary<IntegrityState> = fc.oneof(
  fc.constant({ status: "loading" } as const),
  fc.constant({ status: "error" } as const),
  fc
    .array(fc.constantFrom(...EVIDENCE), { minLength: 1, maxLength: 4 })
    .map((rs) => ({ status: "ok" as const, summary: integritySummary(rs) })),
);

const caseArb = fc.record({
  input: summaryInputArb,
  locale: fc.constantFrom(...routing.locales),
  theme: fc.constantFrom("two-faces" as const, "glass" as const),
  integrity: integrityArb,
});

describe("Summary screen", () => {
  it("P2, P4, P8: abrupt-stop lines, zero state, emergency first, safe wording", () => {
    check(
      fc.property(
        caseArb,
        ({ input: { r, items }, locale, theme, integrity }) => {
          const v = summaryView(r, items, vocabs[locale]);
          const boxes = items.map((it, i) => ({ ...it, boxName: `Box ${i}` }));
          const h = html(
            locale,
            theme,
            <SummaryBody
              result={r}
              items={boxes}
              vocab={vocabs[locale]}
              integrity={integrity}
            />,
          );
          const t = text(h);
          expect(findForbiddenPhrases(t, forbiddenPhrases[locale])).toEqual([]);
          expect(findForbiddenPhrases(t, reassurance[locale])).toEqual([]);
          if (theme === "glass")
            expect(findForbiddenPhrases(t, themeWords[locale])).toEqual([]);
          if (v.kind !== "ok") return;
          // P2: once per warned item.
          expect(h.split('data-testid="abrupt-stop"').length - 1).toBe(
            v.warnedItems.length,
          );
          // P4: no finding → the sentence, and no ring of patterns.
          expect(t.includes(messages[locale].Findings.noPattern)).toBe(
            v.patterns.total === 0,
          );
          expect(h.includes('data-testid="group-fits"')).toBe(
            v.patterns.total > 0,
          );
          // P8: the emergency notice is the first marked element iff a safety line applies.
          const first = /data-testid="([^"]+)"/.exec(h)?.[1];
          expect(first === "emergency-notice").toBe(v.safetyLines.length > 0);
          // Every finding is listed once, under its group.
          expect(h.split('data-testid="summary-finding"').length - 1).toBe(
            v.patterns.total,
          );
          // The discuss sentence with any finding.
          expect(t.includes(messages[locale].Findings.discuss)).toBe(
            v.patterns.total > 0,
          );
          // The integrity sentence only when every line says so.
          if (integrity.status === "ok" && v.patterns.total > 0)
            expect(t.includes(messages[locale].Evidence.line.noRetracted)).toBe(
              integrity.summary.noRetracted,
            );
        },
      ),
      { numRuns: 60 },
    );
  });
});

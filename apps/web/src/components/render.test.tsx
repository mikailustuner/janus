// Feature: experience, Property P8: for any result, memory panel and evidence view, in every
// locale and both themes, the rendered markup has no forbidden phrase and no reassurance word of
// its locale, and Glass markup has no theme-device word (Req 1.3, 6.5, 8.1, 2.4). The disclaimer
// is the shell's footer (once per screen, checked in the browser by C3), so the screen bodies
// must not repeat it.
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
import { cascadeResultArb, EVIDENCE, PAIRS } from "@/test/results";
import { ThemeOverride } from "@/theme/words";
import type { Loaded, Vocabulary, VocabularyIndex } from "@/vocabulary";
import index from "@/vocabulary/index.json";

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: unknown;
  }) => (
    <a {...rest} data-href={String(href)}>
      {children}
    </a>
  ),
  usePathname: () => "/results",
  useRouter: () => ({ push: () => {}, replace: () => {} }),
}));

import { EvidenceBody } from "./evidence/EvidenceView";
import { Home, PATTERNS } from "./home/Home";
import { ISTANBUL_GHOSTS } from "./home/NightPharmacyHero";
import { PairPanel } from "./memory/PairPanel";
import { ResultsBody } from "./results/Results";

type Locale = (typeof routing.locales)[number];
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
const vocabs = Object.fromEntries(
  routing.locales.map((l) => [
    l,
    {
      locale: l,
      vocab: JSON.parse(
        readFileSync(
          join(import.meta.dirname, "../vocabulary", `${l}.json`),
          "utf8",
        ),
      ) as Vocabulary,
      index: index as unknown as VocabularyIndex,
    } satisfies Loaded,
  ]),
) as Record<Locale, Loaded>;

function render(
  locale: Locale,
  theme: "two-faces" | "glass",
  node: React.ReactNode,
): string {
  const html = renderToStaticMarkup(
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      <ThemeOverride.Provider value={theme}>{node}</ThemeOverride.Provider>
    </NextIntlClientProvider>,
  );
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&");
}

function expectSafe(text: string, locale: Locale, theme: string) {
  expect(findForbiddenPhrases(text, forbiddenPhrases[locale])).toEqual([]);
  expect(findForbiddenPhrases(text, reassurance[locale])).toEqual([]);
  if (theme === "glass")
    expect(findForbiddenPhrases(text, themeWords[locale])).toEqual([]);
  expect(text).not.toContain(messages[locale].Disclaimer.text);
}

const target = fc.record({
  locale: fc.constantFrom(...routing.locales),
  theme: fc.constantFrom("two-faces" as const, "glass" as const),
});

describe("rendered screens", () => {
  it("results and finding cards", () => {
    check(
      fc.property(
        cascadeResultArb,
        target,
        ({ result, n }, { locale, theme }) => {
          const boxes = Array.from({ length: n }, (_, i) => `Box ${i}`);
          const text = render(
            locale,
            theme,
            <ResultsBody
              result={result}
              boxNames={boxes}
              vocab={vocabs[locale]}
            />,
          );
          expectSafe(text, locale, theme);
          if (result.statement?.code === "no_pattern_found")
            expect(text).toContain(messages[locale].Findings.noPattern);
        },
      ),
      { numRuns: 60 },
    );
  });
  it("evidence views and FAERS pair panels", () => {
    check(
      fc.property(
        fc.constantFrom(...EVIDENCE),
        fc.constantFrom(...PAIRS),
        target,
        (ev, pair, { locale, theme }) => {
          expectSafe(
            render(locale, theme, <EvidenceBody resolution={ev} />),
            locale,
            theme,
          );
          const panel = render(
            locale,
            theme,
            <PairPanel pair={pair} ingredient="x" event="y" snapshot={null} />,
          );
          expectSafe(panel, locale, theme);
          expect(panel).toContain(messages[locale].Memory.screening);
        },
      ),
      { numRuns: 60 },
    );
  });
});

// Feature: experience, Property P34: the card design keeps every required sentence where it was
// required (Req 29.10, 28.5): the discuss sentence on every finding card, the visible caveats of
// the FAERS pair outside every fold, the integrity line's sentences.
function raw(
  locale: Locale,
  theme: "two-faces" | "glass",
  node: React.ReactNode,
): string {
  return renderToStaticMarkup(
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      <ThemeOverride.Provider value={theme}>{node}</ThemeOverride.Provider>
    </NextIntlClientProvider>,
  ).replace(/&#x27;/g, "'");
}

/** The markup outside every `<details>` element. */
const unfolded = (html: string) =>
  html.replace(/<details[\s\S]*?<\/details>/g, "");

describe("required sentences survive the cards (P34)", () => {
  it("every finding card says it may be worth discussing with the doctor", () => {
    check(
      fc.property(
        cascadeResultArb,
        target,
        ({ result, n }, { locale, theme }) => {
          const boxes = Array.from({ length: n }, (_, i) => `Box ${i}`);
          const html = raw(
            locale,
            theme,
            <ResultsBody
              result={result}
              boxNames={boxes}
              vocab={vocabs[locale]}
            />,
          );
          const cards = html.split('data-testid="finding"').length - 1;
          const discuss = messages[locale].Findings.discuss as string;
          expect(html.split(discuss).length - 1).toBe(cards);
        },
      ),
      { numRuns: 40 },
    );
  });
  it("pair caveats stay outside the fold; the integrity line keeps its sentences", () => {
    check(
      fc.property(
        fc.constantFrom(...EVIDENCE),
        fc.constantFrom(...PAIRS),
        target,
        (ev, pair, { locale, theme }) => {
          const m = messages[locale];
          const panel = unfolded(
            raw(
              locale,
              theme,
              <PairPanel
                pair={pair}
                ingredient="x"
                event="y"
                snapshot={null}
              />,
            ),
          );
          const codes = [
            ...pair.notices,
            ...(pair.status === "ok" ? (pair.stats?.codes ?? []) : []),
            ...(pair.status === "ok" && pair.stats?.assessment
              ? [pair.stats.assessment]
              : []),
          ];
          for (const c of ["spontaneous_reporting", "not_incidence", "weak"])
            if (codes.includes(c)) {
              const sentence = (m.Memory.codes[c] as string).split("{")[0]!;
              expect(panel).toContain(sentence);
            }
          const ev2 = raw(locale, theme, <EvidenceBody resolution={ev} />);
          expect(ev2).toContain('data-testid="integrity-line"');
          expect(ev2).toContain(m.Evidence.line.about);
        },
      ),
      { numRuns: 60 },
    );
  });
});

describe("home (Req 27)", () => {
  it("the pattern count is the rule base's", () => {
    for (const l of routing.locales) {
      const v = JSON.parse(
        readFileSync(join(__dirname, `../vocabulary/${l}.json`), "utf8"),
      ) as Vocabulary;
      expect(Object.keys(v.cascades)).toHaveLength(PATTERNS);
    }
  });

  it("starts with the emergency notice and makes no unsafe claim, in every language and theme", () => {
    for (const locale of routing.locales)
      for (const theme of ["two-faces", "glass"] as const) {
        const html = render(locale, theme, <Home />);
        expectSafe(html, locale, theme);
        const m = messages[locale];
        // The home's slim bar (DP47): its one-line sentence comes first.
        const first = html.indexOf(m.Emergency.line.split("{")[0]!);
        expect(first).toBeGreaterThan(-1);
        expect(first).toBeLessThan(html.indexOf(m.Home.intro));
        expect(html).toContain(m.Home.demo);
        expect(html).toContain(String(PATTERNS));
      }
  });
});

describe("Night Pharmacy ghosts (Req 27.6)", () => {
  it("open the Istanbul demo findings at their recorded positions", () => {
    const fixture = JSON.parse(
      readFileSync(join(__dirname, "../demo/fixtures/istanbul.json"), "utf8"),
    ) as { evaluation: { findings: { rule_id: string; timing: string }[] } };
    const order = fixture.evaluation.findings.map((f) => f.rule_id);
    for (const g of ISTANBUL_GHOSTS) expect(order[g.position]).toBe(g.rule);
    // "then" in the labels of rows 5, 6 and 9 only: their order is known; row 12's is not.
    const timing = (rule: string) =>
      fixture.evaluation.findings.find((f) => f.rule_id === rule)?.timing;
    for (const r of ["pipc:5", "pipc:6", "pipc:9"])
      expect(timing(r)).toBe("within_window");
    expect(timing("pipc:12")).toBe("date_unknown");
    expect(messages.en.Home.ghosts.pipc12).not.toMatch(/\bthen\b/);
    expect(new Set(ISTANBUL_GHOSTS.map((g) => g.rule)).size).toBe(order.length);
  });
});

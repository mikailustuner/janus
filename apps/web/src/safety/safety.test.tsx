// Feature: safety-check, web properties W1–W4 (design §9). Validates Req 7: the section in five
// languages states what was compared, names the medicines by their box names, refers to a
// pharmacist or doctor, never grades and never reads as a clearance.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { NextIntlClientProvider, createTranslator } from "next-intl";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { decode } from "@/api/decode";
import { messageKeyFor } from "@/api/errors";
import { SafetyView } from "@/components/safety/SafetyChecks";
import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "@/i18n/forbidden-phrases";
import { reassurance } from "@/i18n/reassurance";
import { routing } from "@/i18n/routing";
import { check, fc } from "@/test/fc";
import type { Loaded, Vocabulary, VocabularyIndex } from "@/vocabulary";
import index from "@/vocabulary/index.json";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children }: { children: ReactNode }) => <a>{children}</a>,
}));

import { safetyCheckOut, type SafetyCheckOut } from "./model";
import type { SafetyState } from "./useSafety";

type Locale = (typeof routing.locales)[number];
type Tree = { [key: string]: string | Tree };
const read = (path: string) =>
  JSON.parse(readFileSync(join(import.meta.dirname, path), "utf8"));
const catalogues = Object.fromEntries(
  routing.locales.map((l) => [l, read(`../../messages/${l}.json`) as Tree]),
) as Record<Locale, Tree>;
const vocabs = Object.fromEntries(
  routing.locales.map((l) => [
    l,
    {
      locale: l,
      vocab: read(`../vocabulary/${l}.json`) as Vocabulary,
      index: index as unknown as VocabularyIndex,
    } satisfies Loaded,
  ]),
) as Record<Locale, Loaded>;

function flatten(tree: Tree, prefix = ""): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out.set(path, value);
    else for (const [k, v] of flatten(value, path)) out.set(k, v);
  }
  return out;
}
const own = (l: Locale) =>
  new Map(
    [...flatten(catalogues[l])].filter(([k]) => k.startsWith("SafetyCheck.")),
  );
const args = (message: string) =>
  [...message.matchAll(/\{\s*([A-Za-z_]\w*)\s*(?:\}|,)/g)]
    .map((m) => m[1]!)
    .sort();

const fixture = read("fixtures/check.json");
const decoded = decode(safetyCheckOut, fixture);
if (!decoded.ok) throw new Error("fixture does not match the contract");
const sample: SafetyCheckOut = decoded.value;
const ok = (data: SafetyCheckOut): SafetyState => ({ status: "ok", data });
const noneData: SafetyCheckOut = {
  ...sample,
  not_checked: [],
  duplication: {
    ...sample.duplication,
    findings: [],
    statement: { code: "no_duplication_found" },
  },
  interactions: {
    ...sample.interactions,
    findings: [],
    total_findings: 0,
    statement: { code: "no_label_passage_found" },
  },
  burden: {
    ...sample.burden,
    scales: sample.burden.scales.map((s) => ({
      ...s,
      contributions: [],
      total: 0,
    })),
  },
};
const none = ok(noneData);
// Box names stay in the browser; long ones must wrap.
const BOXES = [
  "AMLIPIN 10 / 10",
  "AMLO",
  "RAMI",
  "OMEP",
  "AMLO US",
  "IKIZ",
  "A very long box name that a person typed by hand, with strength 10 mg",
];

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
    .replace(/<blockquote[\s\S]*?<\/blockquote>/g, " ") // a source's words, quoted
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ");

/** Words these texts must never use: forbidden phrases, reassurance, "AI", and grades. */
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
const view = (l: Locale, state: SafetyState, retry?: () => void) =>
  html(
    l,
    <SafetyView
      state={state}
      boxNames={BOXES}
      vocab={vocabs[l]}
      retry={retry}
    />,
  );

describe("W1: the decoder", () => {
  it("accepts the API's answer", () => {
    expect(sample.duplication.findings.map((f) => f.kind)).toEqual([
      "same_ingredient",
      "same_ingredient",
      "same_group",
    ]);
  });

  it("refuses a changed answer", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    type Answer = any;
    const changed: [string, (a: Answer) => void][] = [
      [
        "an unknown kind",
        (a: Answer) => (a.duplication.findings[0].kind = "x"),
      ],
      [
        "a finding with one item",
        (a: Answer) => (a.duplication.findings[0].items = [0]),
      ],
      [
        "a combination code",
        (a: Answer) => (a.duplication.findings[2].atc_group = "C09"),
      ],
      [
        "a finding without members",
        (a: Answer) => (a.duplication.findings[0].members = []),
      ],
      ["another ATC level", (a: Answer) => (a.duplication.atc_level = 3)],
      ["no duplication block", (a: Answer) => delete a.duplication],
      ["no interactions block", (a: Answer) => delete a.interactions],
      ["no burden block", (a: Answer) => delete a.burden],
      [
        "a score outside the published range",
        (a: Answer) => (a.burden.scales[0].contributions[0].score = 4),
      ],
      [
        "a licence page of another kind",
        (a: Answer) =>
          (a.burden.scales[0].license_url = "https://example.org/"),
      ],
      [
        "a scale that is not one of the three",
        (a: Answer) => (a.burden.scales[0].scale_id = "acb"),
      ],
      [
        "a label address elsewhere",
        (a: Answer) =>
          (a.interactions.findings[0].label.url = "https://example.org/x"),
      ],
      [
        "a finding without a passage",
        (a: Answer) => (a.interactions.findings[0].passages = []),
      ],
      [
        "another label statement",
        (a: Answer) => (a.interactions.statement = { code: "all_clear" }),
      ],
      [
        "a statement of another kind",
        (a: Answer) => (a.duplication.statement = { code: "all_clear" }),
      ],
    ];
    for (const [name, change] of changed) {
      const copy = structuredClone(fixture);
      change(copy);
      expect(decode(safetyCheckOut, copy).ok, name).toBe(false);
    }
  });

  it("maps the route's errors to catalogue keys", () => {
    expect(messageKeyFor("safety/check", 503, "safety_unavailable")).toBe(
      "SafetyCheck.errors.unavailable",
    );
    expect(messageKeyFor("safety/check", 409, "dataset_version_mismatch")).toBe(
      "Errors.dataset_changed",
    );
    expect(messageKeyFor("safety/check", 422, "invalid_request")).toBe(
      "Errors.client_defect",
    );
  });
});

describe.each(routing.locales)("SafetyCheck texts, %s", (locale) => {
  const l = locale as Locale;
  const messages = own(l);
  const en = own("en");
  const t = createTranslator({ locale, messages: catalogues[l] as never });

  it("W2: every key of English, with the same parameters", () => {
    expect([...messages.keys()].sort()).toEqual([...en.keys()].sort());
    expect(messages.size).toBeGreaterThanOrEqual(18);
    for (const [key, value] of messages)
      expect(args(value), key).toEqual(args(en.get(key)!));
  });

  it("W2: no forbidden, reassurance or 'AI' word in any text or rendering", () => {
    for (const [key, value] of messages)
      expect(violations(value, l), key).toEqual([]);
    check(
      fc.property(
        fc.constantFrom(...messages.keys()),
        fc.integer({ min: 0, max: 30 }),
        fc.constantFrom("C09AA", "amlodipine", "3 Nov 2026"),
        (key, n, word) => {
          const values: Record<string, string | number> = {};
          for (const name of args(messages.get(key)!))
            values[name] = ["count", "total", "score"].includes(name)
              ? n
              : word;
          const out = t(key as never, values as never) as string;
          expect(violations(out, l), `${key}: ${out}`).toEqual([]);
        },
      ),
    );
  });

  it("W3: nothing found says what was compared and is not a clearance", () => {
    const out = text(view(l, none));
    expect(out).toContain(
      t(
        "SafetyCheck.dup.none" as never,
        { count: sample.ingredients_checked } as never,
      ),
    );
    expect(out).toContain(t("SafetyCheck.review" as never));
    expect(out).toContain(t("SafetyCheck.dup.method" as never));
    expect(out).toMatch(/2026-11-0[67]/); // the data dates of the codes
    expect(out).not.toContain(t("SafetyCheck.dup.advice" as never));
    expect(violations(out, l)).toEqual([]);
  });

  it("W3: a finding names the medicines by their box names, the group and the advice", () => {
    const markup = view(l, ok(sample));
    const out = text(markup);
    expect(markup.match(/data-testid="dup-finding"/g)).toHaveLength(3);
    expect(out).toContain(
      t(
        "SafetyCheck.dup.sameIngredient" as never,
        { ingredient: "amlodipine", count: 3 } as never,
      ).replace("amlodipine", ""),
    );
    expect(out).toContain(
      t(
        "SafetyCheck.dup.sameGroup" as never,
        { group: "C09AA", count: 3 } as never,
      ),
    );
    for (const box of ["AMLIPIN 10 / 10", "AMLO US", "RAMI", BOXES[6]!])
      expect(out).toContain(box);
    expect(out).not.toContain("OMEP");
    expect(out).toContain("C09AA03");
    expect(out).toContain(t("SafetyCheck.dup.unconfirmed" as never));
    expect(out).toContain(t("SafetyCheck.dup.advice" as never));
    expect(out).toContain(t("SafetyCheck.review" as never));
    expect(out).toContain(
      t("SafetyCheck.notChecked" as never, { count: 1 } as never),
    );
    expect(violations(out, l)).toEqual([]);
    // Not an alert: no red and no warning colour (design.md shared rules).
    expect(markup).not.toMatch(/(text|border|bg)-(risk|warn)/);
  });

  it("W3: a label passage is quoted with its label, date and link, and not judged", () => {
    const markup = view(l, ok(sample));
    const out = text(markup);
    const finding = sample.interactions.findings[0]!;
    expect(markup.match(/data-testid="int-finding"/g)).toHaveLength(1);
    expect(markup).toMatch(
      /<blockquote[^>]*lang="en"[^>]*>Co-administration with ramipril was studied\.<\/blockquote>/,
    );
    expect(markup).toContain(`href="${finding.label.url}"`);
    expect(markup).toMatch(/rel="noopener noreferrer"/);
    expect(out).toContain("2026-02-03");
    expect(out).toContain(finding.label.set_id);
    expect(out).toContain(t("SafetyCheck.int.quote" as never));
    expect(out).toContain(t("SafetyCheck.int.advice" as never));
    expect(out).toContain(t("SafetyCheck.int.method" as never));
    expect(out).toContain(
      t("SafetyCheck.int.source" as never, { date: "2026-11-03" } as never),
    );
    expect(out).toContain("AMLIPIN 10 / 10");
    expect(out).toContain("RAMI");
    expect(violations(out, l)).toEqual([]);
    expect(markup).not.toMatch(/(text|border|bg)-(risk|warn)/);
  });

  it("W3: label text, nothing found: what was read, not a clearance; unavailable says so", () => {
    const out = text(view(l, none));
    expect(out).toContain(
      t("SafetyCheck.int.none" as never, { count: 1 } as never),
    );
    expect(out).toContain("AMLODIPINE BESYLATE");
    const [head, tail] = t(
      "SafetyCheck.int.notFound" as never,
      { names: "§" } as never,
    ).split("§");
    expect(out).toContain(head);
    expect(out).toContain(tail);
    expect(out).not.toContain(t("SafetyCheck.int.advice" as never));
    const off = view(
      l,
      ok({
        ...sample,
        interactions: {
          ...sample.interactions,
          status: "unavailable",
          source: null,
          findings: [],
          labels_read: [],
          labels_not_found: [],
          statement: null,
        },
      }),
    );
    expect(off).toContain('data-testid="int-unavailable"');
    expect(text(off)).toContain(t("SafetyCheck.int.unavailable" as never));
    expect(text(off)).toContain(
      t(
        "SafetyCheck.dup.sameGroup" as never,
        { group: "C09AA", count: 3 } as never,
      ),
    );
  });

  it("W3: burden: contributing medicines with the published score, the sum, the citation; no grade", () => {
    const markup = view(l, ok(sample));
    const out = text(markup);
    expect(markup.match(/data-testid="burden-scale"/g)).toHaveLength(3);
    const first = sample.burden.scales[0]!;
    expect(first.contributions.length).toBeGreaterThan(0);
    expect(out).toContain(first.title);
    expect(out).toContain(
      t("SafetyCheck.burden.total" as never, { total: first.total } as never),
    );
    expect(out).toContain(
      t("SafetyCheck.burden.score" as never, { score: 3 } as never),
    );
    expect(out).toContain("Amitriptyline");
    expect(out).toContain(first.citation);
    expect(out).toContain(t("SafetyCheck.burden.advice" as never));
    expect(out).toContain(t("SafetyCheck.burden.method" as never));
    expect(markup).toContain(`href="${first.url}"`);
    expect(violations(out, l)).toEqual([]);
    expect(markup).not.toMatch(/(text|border|bg)-(risk|warn)/);
    expect(out).not.toMatch(/\b(ACB|ARS|ADS)\b/);
  });

  it("W3: burden, no listed ingredient: how many drugs the scale lists, not a clearance", () => {
    const markup = view(l, none);
    const out = text(markup);
    expect(markup.match(/data-testid="burden-none"/g)).toHaveLength(3);
    expect(out).toContain(
      t("SafetyCheck.burden.none" as never, { count: 151 } as never),
    );
    expect(out).not.toContain(t("SafetyCheck.burden.advice" as never));
    expect(markup).not.toContain('data-testid="burden-total"');
    expect(violations(out, l)).toEqual([]);
  });

  it("W3: loading and error with retry", () => {
    const loading = view(l, { status: "loading" });
    expect(loading).toContain('role="status"');
    expect(loading).toContain('aria-busy="true"');
    const failed = view(
      l,
      {
        status: "error",
        error: {
          kind: "http",
          route: "safety/check",
          status: 503,
          code: "safety_unavailable",
          fields: [],
          messageKey: "SafetyCheck.errors.unavailable",
        },
      },
      () => {},
    );
    expect(failed).toContain('role="alert"');
    expect(text(failed)).toContain(
      t("SafetyCheck.errors.unavailable" as never),
    );
    expect(text(failed)).toContain(t("Common.retry" as never));
    expect(failed).not.toContain('data-testid="dup-');
  });
});

describe("W4: what is rendered is what the answer names", () => {
  const key = fc.constantFrom("Q1", "Q2", "Q3", "J1");
  const member = fc.record({
    ingredient_key: key,
    label_en: fc.constantFrom(null, "name one", "name two"),
    items: fc.uniqueArray(fc.integer({ min: 0, max: 6 }), {
      minLength: 1,
      maxLength: 4,
    }),
    codes: fc.constantFrom<string[]>(["C09AA03"], ["C09AA03", "C09AA05"]),
    form_confirmed: fc.boolean(),
  });
  const finding = fc
    .record({
      kind: fc.constantFrom("same_ingredient" as const, "same_group" as const),
      members: fc.uniqueArray(member, {
        minLength: 2,
        maxLength: 3,
        selector: (m) => m.ingredient_key,
      }),
    })
    .map(({ kind, members }) => {
      const ms = kind === "same_ingredient" ? members.slice(0, 1) : members;
      return {
        finding_id: `${kind}:${ms[0]!.ingredient_key}`,
        kind,
        atc_group: kind === "same_group" ? "C09AA" : null,
        members: ms,
        items: [...new Set(ms.flatMap((m) => m.items))].sort(),
        form_confirmed: ms.every((m) => m.form_confirmed),
      };
    });

  it("one row per (member, item); only box names of named items; never a list position", () => {
    check(
      fc.property(
        fc.uniqueArray(finding, {
          maxLength: 3,
          selector: (f) => f.finding_id,
        }),
        (findings) => {
          const data: SafetyCheckOut = {
            ...noneData,
            duplication: {
              ...sample.duplication,
              findings,
              statement: findings.length
                ? null
                : { code: "no_duplication_found" },
            },
          };
          const markup = view("en", ok(data));
          const rows = findings.reduce(
            (n, f) => n + f.members.reduce((k, m) => k + m.items.length, 0),
            0,
          );
          expect(
            (markup.match(/<li class="flex flex-wrap items-baseline/g) ?? [])
              .length,
          ).toBe(rows);
          const named = new Set(
            findings.flatMap((f) => f.members.flatMap((m) => m.items)),
          );
          const out = text(markup);
          BOXES.forEach((box, i) => {
            if (i === 1) return; // "AMLO" is a prefix of "AMLO US"
            expect(out.includes(box)).toBe(named.has(i));
          });
          expect(markup.includes('data-testid="dup-none"')).toBe(
            findings.length === 0,
          );
        },
      ),
    );
  });
});

it("the English reference texts of Req 7 are kept", () => {
  const en = own("en");
  expect(en.get("SafetyCheck.review")).toBe(
    "Expert review has not yet been done.",
  );
  expect(en.get("SafetyCheck.intro")).toContain("Automated comparisons");
  expect(en.get("SafetyCheck.dup.none")).toMatch(
    /This does not mean your medicines are free of problems\.$/,
  );
  expect(en.get("SafetyCheck.dup.advice")).toContain(
    "A pharmacist or doctor can look at it with you.",
  );
});

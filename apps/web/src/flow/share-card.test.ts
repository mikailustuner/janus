// Feature: janus-report, Properties P6, P7 (design §6): the share image's text model holds no box
// name, and no event or ingredient name unless the person opted in (sentinel names); the
// disclaimer is always there, the demo label iff demo, the no-pattern sentence iff no finding, the
// abrupt-stop sentence iff a warned item, safety lines only together with event names.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { createTranslator } from "next-intl";
import { describe, expect, it } from "vitest";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "@/i18n/forbidden-phrases";
import { reassurance } from "@/i18n/reassurance";
import { routing } from "@/i18n/routing";
import { check, fc } from "@/test/fc";
import { VOCAB_EN } from "@/test/results";
import { summaryInputArb } from "@/test/summary";
import type { Translate } from "@/theme/words";

import { shareCard, shareCardText } from "./share-card";
import { summaryView } from "./summary";

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
) as Record<Locale, Record<string, Record<string, unknown>>>;
const translators = Object.fromEntries(
  routing.locales.map((l) => [
    l,
    createTranslator({
      locale: l,
      messages: messages[l]!,
    }) as unknown as Translate,
  ]),
) as Record<Locale, Translate>;

const EVENT = (i: number) => `ZZSENTINEL-EVENT-${i}`;
const INGREDIENT = (i: number) => `ZZSENTINEL-INGREDIENT-${i}`;
const BOX = "ZZSENTINEL-BOX";
const SAFETY = "ZZSENTINEL-SAFETY";

const caseArb = fc.record({
  input: summaryInputArb,
  locale: fc.constantFrom(...routing.locales),
  events: fc.boolean(),
  ingredients: fc.boolean(),
  demo: fc.boolean(),
  safety: fc.boolean(),
});

function build(c: {
  input: {
    r: Parameters<typeof summaryView>[0];
    items: Parameters<typeof summaryView>[1];
  };
  locale: Locale;
  events: boolean;
  ingredients: boolean;
  demo: boolean;
  safety: boolean;
}) {
  const v = summaryView(c.input.r, c.input.items, VOCAB_EN);
  if (v.kind !== "ok") return null;
  const t = translators[c.locale];
  const card = shareCard({
    view: v,
    options: { events: c.events, ingredients: c.ingredients },
    demo: c.demo,
    eventNames: v.findings.map((f) => EVENT(f.position)),
    ingredientNames: c.input.items.map((_, i) => INGREDIENT(i)),
    safetyTexts: c.safety ? [SAFETY] : [],
    emergencyText: "ZZSENTINEL-EMERGENCY",
    abruptStop: "Do not stop this medicine suddenly.",
    month: "November 2026",
    t,
    formatNumber: (n) => String(n),
  });
  return { v, card, text: shareCardText(card) };
}

describe("shareCard", () => {
  it("P6: no box name ever; event and ingredient names only when opted in", () => {
    check(
      fc.property(caseArb, (c) => {
        const out = build(c);
        if (!out) return;
        const { v, text } = out;
        expect(text).not.toContain(BOX);
        const hasEvents = v.findings.length > 0;
        for (const f of v.findings)
          expect(text.includes(EVENT(f.position))).toBe(c.events);
        if (!c.events || !hasEvents)
          expect(text).not.toContain("ZZSENTINEL-EVENT");
        c.input.items.forEach((_, i) =>
          expect(text.includes(INGREDIENT(i))).toBe(c.ingredients),
        );
        // Safety lines and the emergency notice only with event names that carry one.
        expect(text.includes(SAFETY)).toBe(c.events && hasEvents && c.safety);
        expect(text.includes("ZZSENTINEL-EMERGENCY")).toBe(
          c.events && hasEvents && c.safety,
        );
      }),
    );
  });

  it("P7: disclaimer always, demo label iff demo, zero and abrupt-stop sentences when they apply", () => {
    check(
      fc.property(caseArb, (c) => {
        const out = build(c);
        if (!out) return;
        const { v, text } = out;
        const m = messages[c.locale]!;
        expect(text).toContain((m.Disclaimer as { text: string }).text);
        expect(text.includes((m.Demo as { label: string }).label)).toBe(c.demo);
        const noPattern = (m.Findings as { noPattern: string }).noPattern;
        expect(text.includes(noPattern)).toBe(v.patterns.total === 0);
        expect(text.includes("Do not stop this medicine suddenly.")).toBe(
          v.warnedItems.length > 0,
        );
        expect(findForbiddenPhrases(text, forbiddenPhrases[c.locale])).toEqual(
          [],
        );
        expect(findForbiddenPhrases(text, reassurance[c.locale])).toEqual([]);
      }),
    );
  });
});

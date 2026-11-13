// Feature: model-kit gate study (DP-M40). The validation section explains the leave-one-study-out
// design and counts the points whose study also builds the set shown, in every language.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { routing } from "@/i18n/routing";
import type { DrugOut } from "@/modelkit/model";
import { KEYS, modelKitSet } from "@/test/fixtures/modelkit";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children }: { children: ReactNode }) => <a>{children}</a>,
  useRouter: () => ({ replace: () => undefined, push: () => undefined }),
  usePathname: () => "/",
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: () => undefined, push: () => undefined }),
  usePathname: () => "/",
}));

import { Validation } from "./ModelKitDrug";

type Locale = (typeof routing.locales)[number];
const messages = (l: Locale) =>
  JSON.parse(
    readFileSync(
      join(import.meta.dirname, `../../../messages/${l}.json`),
      "utf8",
    ),
  ) as { ModelKit: { val: Record<string, string> } };

const drugs = modelKitSet().drug;
const validated = () => drugs[KEYS.validated]!;
// a drug with validation points
const withPoints = () => drugs[KEYS.validated]!;

const html = (locale: Locale, out: DrugOut) =>
  renderToStaticMarkup(
    <NextIntlClientProvider
      locale={locale}
      messages={messages(locale) as never}
      timeZone="UTC"
    >
      <Validation out={out} />
    </NextIntlClientProvider>,
  );

describe("leave-one-study-out validation", () => {
  it("the answer names the design", () => {
    expect(validated().validation.design).toBe("leave_one_study_out");
  });

  it("counts rebuilt points only when there are some, in every language", () => {
    const base = withPoints();
    expect(base.validation.points.length).toBeGreaterThan(0);
    const plain: DrugOut = {
      ...base,
      validation: {
        ...base.validation,
        points: base.validation.points.map((p) => ({
          ...p,
          rebuilt_without_study: false,
        })),
      },
    };
    const rebuilt: DrugOut = {
      ...plain,
      validation: {
        ...plain.validation,
        points: plain.validation.points.map((p) => ({
          ...p,
          rebuilt_without_study: true,
        })),
      },
    };
    const n = plain.validation.points.length;
    for (const l of routing.locales) {
      expect(html(l, plain)).not.toContain('data-testid="mk-rebuilt"');
      const out = html(l, rebuilt);
      expect(out).toContain('data-testid="mk-rebuilt"');
      const intro = messages(l).ModelKit.val.intro!;
      expect(out).toContain(intro.slice(0, 30));
      expect(out).toMatch(new RegExp(`\\b${n}\\b`));
    }
  });
});

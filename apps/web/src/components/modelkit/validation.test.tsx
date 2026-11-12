// Feature: model-kit gate study (DP-M39). The validation section explains the leave-one-study-out
// design and counts the points whose study also builds the set shown, in every language.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { decode } from "@/api/decode";
import { routing } from "@/i18n/routing";
import { drugOut, type DrugOut } from "@/modelkit/model";
import recorded from "@/modelkit/modelkit.recorded.json";

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

function enzalutamide(): DrugOut {
  const r = decode(drugOut, recorded.drug.enzalutamide);
  if (!r.ok) throw new Error("recorded drug does not decode");
  return r.value;
}

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
  it("the recorded answer names the design", () => {
    expect(enzalutamide().validation.design).toBe("leave_one_study_out");
  });

  it("counts rebuilt points only when there are some, in every language", () => {
    const plain = enzalutamide();
    expect(plain.validation.points.length).toBeGreaterThan(0);
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

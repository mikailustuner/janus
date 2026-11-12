// Feature: model-kit milestone M6 (plan 6.4). The review line says "Expert review has not yet been
// done." until an expert audit record is in the answer; with one it gives precision, n and date,
// in five languages, and never a name.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { NextIntlClientProvider } from "next-intl";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { decode } from "@/api/decode";
import { routing } from "@/i18n/routing";
import { drugsOut, type ExpertAudit } from "@/modelkit/model";
import recorded from "@/modelkit/modelkit.recorded.json";

import { Statements } from "./common";

type Locale = (typeof routing.locales)[number];
const messages = (l: Locale) =>
  JSON.parse(
    readFileSync(
      join(import.meta.dirname, `../../../messages/${l}.json`),
      "utf8",
    ),
  ) as Record<string, Record<string, string>>;

const AUDIT: ExpertAudit = {
  date: "2027-01-15",
  release_audited: "20261112T135125Z-8ac5398b-3c00",
  n_items: 366,
  n: 320,
  correct: 310,
  cannot_judge: 30,
  precision: 310 / 320,
  wilson_low: 0.9435,
  wilson_high: 0.983,
  criterion_met: true,
  reviewer_roles: ["clinical_pharmacologist", "pharmacometrician"],
};

const html = (locale: Locale, audit: ExpertAudit | null) =>
  renderToStaticMarkup(
    <NextIntlClientProvider
      locale={locale}
      messages={messages(locale) as never}
      timeZone="UTC"
    >
      <Statements recorded={null} audit={audit} />
    </NextIntlClientProvider>,
  );

describe("expert review line", () => {
  it("is the pending sentence without an audit record, in every language", () => {
    for (const l of routing.locales) {
      const out = html(l, null);
      expect(out).toContain(messages(l).ModelKit!.expertReview!);
      expect(out).toContain('data-audit="no"');
    }
  });

  it("gives precision, n and date with an audit record, in every language", () => {
    for (const l of routing.locales) {
      const out = html(l, AUDIT);
      expect(out).not.toContain(messages(l).ModelKit!.expertReview!);
      expect(out).toContain('data-audit="yes"');
      expect(out).toContain("n = 320");
      expect(out).toContain("2027\u201101\u201115");
      expect(out).toMatch(/0[.,]97/);
    }
    expect(html("en", AUDIT)).toContain(
      "Expert audit: precision 0.97 (n = 320, 2027\u201101\u201115).",
    );
    expect(html("tr", AUDIT)).toContain("0,97");
  });

  it("the recorded release has no audit record (the live text is unchanged)", () => {
    const d = decode(drugsOut, recorded.drugs);
    expect(d.ok).toBe(true);
    if (d.ok) {
      expect(d.value.statements.expert_audit).toBeNull();
      expect(d.value.statements.expert_review).toBe(
        "Expert review has not yet been done.",
      );
    }
  });
});

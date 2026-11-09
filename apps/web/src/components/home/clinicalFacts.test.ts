// Feature: experience, Property P41 (Req 31.5, DP70): the figures of the Glass Janus home are the
// recorded Istanbul demo, and no Glass home text carries another number (the pattern count,
// PATTERNS, is checked against the rule base in src/components/render.test.tsx).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { routing } from "@/i18n/routing";

import { DEMO_FINDING } from "./clinicalFacts";

const web = join(import.meta.dirname, "../../..");
const read = (p: string) => JSON.parse(readFileSync(join(web, p), "utf8"));

type Finding = {
  finding_id: string;
  months_between: number;
  index: { label_en: string };
  marker: { label_en: string };
};

describe("Glass Janus home figures", () => {
  const demo = read("src/demo/fixtures/istanbul.json");
  const finding = (demo.evaluation.findings as Finding[]).find(
    (f) => f.finding_id === DEMO_FINDING.findingId,
  );

  it("the hero finding is the recorded amlodipine → furosemide finding", () => {
    expect(finding).toBeDefined();
    expect(finding!.index.label_en).toBe("amlodipine");
    expect(finding!.marker.label_en).toBe("furosemide");
    expect(finding!.months_between).toBe(DEMO_FINDING.monthsBetween);
    expect(demo.evidence[DEMO_FINDING.findingId].line.sources_total).toBe(
      DEMO_FINDING.sources,
    );
  });

  it.each(routing.locales)(
    "%s: the Glass home texts carry no number but the PIPC year",
    (locale) => {
      const home = read(`messages/${locale}.json`).Home.glass as Record<
        string,
        string
      >;
      for (const [key, text] of Object.entries(home)) {
        const digits = text.replace(/\{[^{}]*\}/g, "").match(/\d+/g) ?? [];
        expect(
          digits.filter((d) => d !== "2025"),
          key,
        ).toEqual([]);
      }
    },
  );
});

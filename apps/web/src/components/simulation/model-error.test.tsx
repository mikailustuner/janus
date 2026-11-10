// simulation-service property S9 (owner decision 2026-11-09): measured model error with every
// result. Every httk result renders its measured bias against Obach 2008 and the calibrated 80 %
// interval, which exists only for half-life; compartmental results render no calibrated interval
// and say they are not validated beyond one study; invalid ADMET-AI half-life and VDss values
// (zero or below) are never shown as numbers.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import fc from "fast-check";
import { NextIntlClientProvider } from "next-intl";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { admetUsable } from "@/components/timemachine/SubstanceView";
import * as D from "@/api/decode";
import { httkResult, type HttkResult } from "@/simulation/client";
import recorded from "@/simulation/simulate.recorded.json";

import { EXPLORER } from "@/simulation/explorer";

import { CompartmentalModelNote, HttkResultView } from "./common";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
  usePathname: () => "/research/simulate",
  useRouter: () => ({ push: () => {}, replace: () => {} }),
}));

const LOCALES = ["en", "tr", "de", "fr", "es"] as const;
const messages = Object.fromEntries(
  LOCALES.map((l) => [
    l,
    JSON.parse(
      readFileSync(
        join(import.meta.dirname, `../../../messages/${l}.json`),
        "utf8",
      ),
    ),
  ]),
);

const httkJob = (
  recorded as { jobs: { job: { result: unknown } }[] }
).jobs.find((j) => (j.job.result as { model?: string }).model === "httk")!;
const decoded = D.decode(httkResult, httkJob.job.result);
if (!decoded.ok) throw new Error("recorded httk result does not decode");
const base = decoded.value;

const render = (locale: (typeof LOCALES)[number], node: React.ReactNode) =>
  renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} messages={messages[locale]}>
      {node}
    </NextIntlClientProvider>,
  );

const fmt = (locale: string, x: number) =>
  new Intl.NumberFormat(locale, { maximumSignificantDigits: 3 }).format(x);

describe("S9: measured model error", () => {
  it("every httk result shows its bias against Obach 2008 and the half-life interval", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...LOCALES),
        fc.double({ min: 0.1, max: 2000, noNaN: true }),
        fc.double({ min: 0.5, max: 3, noNaN: true }),
        (locale, t, ratio) => {
          const w = 87.4 ** 0.5;
          const r: HttkResult = {
            ...base,
            half_life_h: t,
            half_life_interval_h: [t / w, t * w],
            older_to_younger_median_ratio: ratio,
          };
          const html = render(
            locale,
            <HttkResultView r={r} compound="haloperidol" />,
          );
          expect(html).toContain('data-testid="sim-bias"');
          expect(html).toContain("Obach 2008");
          expect(html).toContain(fmt(locale, base.model_error.half_life.gmfe));
          expect(html).toContain('data-testid="sim-interval-label"');
          expect(html).toContain(fmt(locale, t * w));
          expect(html).toContain('data-testid="sim-not-validated"');
          expect(html).toContain('data-testid="sim-older-note"');
          expect(html).toContain("httk-pop-older-adult-exposure.md");
        },
      ),
      { numRuns: 40 },
    );
  });

  it("a label half-life is shown with its route, set id and sentence, and only where one exists", () => {
    const labelled = EXPLORER.label_half_life.drugs;
    expect(Object.keys(labelled)).toContain("metoclopramide");
    for (const locale of LOCALES) {
      for (const compound of ["metoclopramide", "haloperidol", "risperidone"]) {
        const html = render(
          locale,
          <HttkResultView r={base} compound={compound} />,
        );
        // Next to the ratio: it is not drug-specific.
        expect(html).toContain(
          messages[locale].Simulation.olderAdults.notDrugSpecific.replaceAll(
            "'",
            "&#x27;",
          ),
        );
        const rows = labelled[compound] ?? [];
        expect(html.includes('data-testid="label-half-life"')).toBe(
          rows.length > 0,
        );
        for (const r of rows) {
          expect(html).toContain(r.set_id);
          expect(html).toContain(`<q lang="en">${r.sentence}</q>`);
          expect(html).toContain(
            messages[locale].Simulation.labelHalfLife.route[r.route],
          );
        }
      }
    }
  });

  it("the recorded httk run carries the calibrated interval around its half-life", () => {
    const [lo, hi] = base.half_life_interval_h;
    expect(lo! < base.half_life_h && base.half_life_h < hi!).toBe(true);
    expect(hi! / lo!).toBeCloseTo(87.4, 6);
    expect(base.model_error.concentrations_validated).toBe(false);
  });

  it("compartmental results render no calibrated interval and say what is not validated", () => {
    for (const locale of LOCALES) {
      const html = render(locale, <CompartmentalModelNote />);
      expect(html).toContain(
        messages[locale].Simulation.modelError.compartmental.split(":")[0],
      );
      expect(html).not.toContain("Obach");
    }
  });

  it("invalid ADMET-AI half-life and VDss values are never shown", () => {
    fc.assert(
      fc.property(
        fc.constantFrom("Half_Life_Obach", "VDss_Lombardo"),
        fc.double({ max: 0, noNaN: true }),
        (name, v) => {
          expect(admetUsable(name, v)).toBe(false);
        },
      ),
    );
    expect(admetUsable("Half_Life_Obach", 0)).toBe(false);
    expect(admetUsable("VDss_Lombardo", 1.2)).toBe(true);
  });
});

// The generated validation numbers equal a fresh derivation from the committed result files (run
// `pnpm gen:validation` after a data change), and the view model formats them without altering them.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { generate } from "../../scripts/gen-validation.mjs";
import { serialise } from "../../scripts/gen-vocabulary.mjs";

import {
  calibrationValues,
  hypothesisKey,
  percent,
  proportionValues,
  shareValues,
  VALIDATION,
} from "./validation";

const repoRoot = join(import.meta.dirname, "../../../..");

describe("validation.generated.json", () => {
  it("equals the generator output (run `pnpm gen:validation` after a data change)", () => {
    expect(
      readFileSync(
        join(import.meta.dirname, "validation.generated.json"),
        "utf8",
      ),
    ).toBe(serialise(generate(repoRoot)));
  });

  it("holds the registered numbers and the hypothesis outcomes", () => {
    const { cascade, faers } = VALIDATION;
    expect([cascade.specificity.k, cascade.specificity.n]).toEqual([421, 432]);
    expect([cascade.sensitivity.k, cascade.sensitivity.n]).toEqual([79, 217]);
    expect(cascade.specificity.met).toBe(true);
    expect(cascade.sensitivity.met).toBe(false);
    expect(cascade.inScope).toEqual({ k: 77, n: 77 });
    expect(cascade.listedCascades).toBe(65);
    expect(cascade.caseReports).toBe(107);
    expect(faers.auc.met).toBe(true);
    expect(cascade.protocolUrl).toMatch(/^https:\/\/github\.com\//);
  });
});

describe("view model", () => {
  it("formats with the locale and keeps the rounded values", () => {
    expect(proportionValues(VALIDATION.cascade.specificity, "en")).toEqual({
      k: "421",
      n: "432",
      estimate: "0.975",
      low: "0.955",
      high: "0.986",
    });
    expect(
      proportionValues(VALIDATION.cascade.sensitivity, "tr").estimate,
    ).toBe("0,364");
    expect(shareValues(VALIDATION.faers.negativesNominal, "en")).toEqual({
      estimate: "26%",
      low: "21%",
      high: "32%",
    });
    expect(percent(0.0526, "en", 1)).toBe("5.3%");
  });

  it("gives the calibration line values", () => {
    expect(calibrationValues("en")).toEqual({
      auc: "0.74",
      low: "0.69",
      high: "0.78",
    });
  });

  it("maps the outcome to a message key", () => {
    expect(hypothesisKey(true)).toBe("ValidationStudies.met");
    expect(hypothesisKey(false)).toBe("ValidationStudies.notMet");
  });
});

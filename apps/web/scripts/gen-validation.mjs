/**
 * Generates src/research/validation.generated.json: exactly the numbers the Validation screens
 * show, read from the committed results of the two pre-registered studies (docs/research/). Nothing
 * is typed by hand: counts, estimates and intervals come from the metrics files, the protocol
 * commit from the results document, the listed-cascade count from data/pipc.csv. The hypothesis
 * thresholds are those of the protocols. A vitest test regenerates in memory and compares.
 *
 *   node apps/web/scripts/gen-validation.mjs      write src/research/validation.generated.json
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { parseCsv, serialise } from "./gen-vocabulary.mjs";

const REPO = "https://github.com/mikailustuner/janus";
const DOCS = `${REPO}/blob/main/docs/research`;

/** Pre-registered thresholds (protocols): cascade H1 sensitivity lower bound 0.80, H2 specificity
 * lower bound 0.90; FAERS AUC lower bound above 0.5. */
const THRESHOLD = { h1: 0.8, h2: 0.9, auc: 0.5 };

const read = (root, path) => readFileSync(join(root, path), "utf8");
const json = (root, path) => JSON.parse(read(root, path));

/** A proportion with its interval, as the UI shows it. */
function prop(m) {
  return {
    k: m.k,
    n: m.n,
    estimate: m.estimate,
    low: m.ci95_low,
    high: m.ci95_high,
  };
}

function commit(text, label) {
  const m = /registered in (?:commit\s+)?`([0-9a-f]{7,40})`/.exec(
    text.replace(/\s+/g, " "),
  );
  if (!m) throw new Error(`no protocol commit in ${label}`);
  return m[1];
}

function measure(list, name) {
  const m = list.find((x) => x.measure === name);
  if (!m) throw new Error(`measure ${name} missing`);
  return m;
}

export function generate(root) {
  const cm = json(root, "data/validation/cascades/results/metrics.json");
  const ce = json(root, "data/validation/cascades/results/errors.json");
  const fm = json(root, "data/validation/faers/results/metrics.json");
  const all = [...cm.primary, ...cm.secondary];
  const sens = measure(all, "sensitivity_pairs");
  const spec = measure(all, "specificity_pairs");
  const cases = measure(all, "case_detection");
  const comparison = measure(all, "comparison_alert_rate");
  const listed = parseCsv(read(root, "data/pipc.csv")).length;
  const auc = fm.primary_auc_ln_ror;
  const s = fm.secondary;
  return {
    cascade: {
      protocolCommit: commit(
        read(root, "docs/research/cascade-validation.md"),
        "cascade-validation.md",
      ),
      protocolUrl: `${DOCS}/cascade-validation-protocol.md`,
      resultsUrl: `${DOCS}/cascade-validation.md`,
      listedCascades: listed,
      publishedCascades: sens.n,
      nonCascadePairs: spec.n,
      caseReports: cases.n + comparison.n,
      specificity: {
        ...prop(spec),
        bound: THRESHOLD.h2,
        met: spec.ci95_low >= THRESHOLD.h2,
      },
      sensitivity: {
        ...prop(sens),
        bound: THRESHOLD.h1,
        met: sens.ci95_low >= THRESHOLD.h1,
      },
      inScope: {
        k: ce.within_rule_base_scope.flagged,
        n: ce.within_rule_base_scope.pairs,
      },
      comparisonAlert: prop(comparison),
    },
    faers: {
      protocolCommit: commit(
        read(root, "docs/research/faers-calibration.md"),
        "faers-calibration.md",
      ),
      protocolUrl: `${DOCS}/faers-calibration-protocol.md`,
      resultsUrl: `${DOCS}/faers-calibration.md`,
      auc: {
        estimate: auc.auc,
        low: auc.ci95_low,
        high: auc.ci95_high,
        nPositive: auc.n_pos,
        nNegative: auc.n_neg,
        bound: THRESHOLD.auc,
        met: auc.ci95_low > THRESHOLD.auc,
      },
      negativesNominal: prop(s.negatives_ci_excluding_1_nominal),
      negativesCalibrated: prop(
        s.negatives_p_below_005_calibrated_leave_one_out,
      ),
      evansSensitivity: prop(s.evans_sensitivity),
      evansSpecificity: prop(s.evans_specificity),
    },
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const here = fileURLToPath(new URL(".", import.meta.url));
  const repoRoot = join(here, "../../..");
  writeFileSync(
    join(here, "../src/research/validation.generated.json"),
    serialise(generate(repoRoot)),
  );
  console.log("validation numbers written");
}

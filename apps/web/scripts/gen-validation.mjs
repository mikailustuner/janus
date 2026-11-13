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
 * lower bound 0.90; FAERS AUC lower bound above 0.5; model kit precision cluster-aware lower bound
 * 0.90 (the "acceptance_rule" of precision.json). */
const THRESHOLD = { h1: 0.8, h2: 0.9, auc: 0.5, precision: 0.9 };

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

const need = (x, label) => {
  if (x === undefined || x === null) throw new Error(`${label} missing`);
  return x;
};

/** One row of the model kit precision table from a measured point. */
function precisionRow(key, point, shipsKey) {
  return {
    key,
    values: point.n,
    studies: point.studies,
    precision: point.precision,
    wilsonLow: point.wilson[0],
    wilsonHigh: point.wilson[1],
    clusterLower: point.cluster_lower,
    met: shipsKey,
  };
}

function modelkit(root) {
  const pr = json(root, "data/validation/modelkit/precision.json");
  const gt = json(root, "data/validation/modelkit/gate.json");
  const src = pr.sources;
  const ct = src.clinicaltrials_gov;
  const pmc = src.pmc_oa;
  const fda = src.drugsatfda_review;
  const pmcPoint = pmc.curves[0].points.find(
    (p) => p.level === pmc.acceptance.levels_tested[0],
  );
  const fdaPoint = fda.curves[0].points.find(
    (p) => p.level === fda.acceptance.levels_tested[0],
  );
  const curve = ct.curves[0];
  const rows = Object.fromEntries(gt.rows.map((r) => [r.id, r]));
  const row = (id) => need(rows[id], `gate row ${id}`);
  const num = (id) => row(id).numbers;
  const g = gt.gate;
  const cc = gt.claim;
  const x = gt.cross_study_check;
  const ids = [
    "values_read_correctly",
    "auc_within_2_fold",
    "cmax_within_2_fold",
    "gate",
    "drug_validated",
    "document_sources",
    "unit_errors_across_studies",
    "recall",
    "special_populations",
    "expert_review",
  ];
  return {
    precision: {
      protocolCommit: commit(
        read(root, "docs/research/modelkit-precision.md"),
        "modelkit-precision.md",
      ),
      protocolUrl: `${DOCS}/modelkit-precision-protocol.md`,
      resultsUrl: `${DOCS}/modelkit-precision.md`,
      bound: THRESHOLD.precision,
      sources: [
        {
          ...precisionRow(
            "clinicaltrials_gov",
            ct.shipped,
            ct.shipped.meets_rule,
          ),
          confirmed: ct.confirmed_values,
          level: ct.shipped.level,
        },
        {
          ...precisionRow("pmc_oa", pmcPoint, pmc.acceptance.ships),
          confirmed: pmc.confirmed_values,
          level: pmcPoint.level,
        },
        {
          ...precisionRow("drugsatfda_review", fdaPoint, fda.acceptance.ships),
          confirmed: fda.confirmed_values,
          level: fdaPoint.level,
        },
      ],
      curve: curve.points.map((p) => ({
        level: p.level,
        coverage: p.coverage,
        precision: p.precision,
        clusterLower: p.cluster_lower,
        met: p.meets_rule,
      })),
      curveValues: curve.frame_values,
    },
    gate: {
      protocolCommit: commit(
        read(root, "docs/research/modelkit-gate.md"),
        "modelkit-gate.md",
      ),
      protocolUrl: `${DOCS}/modelkit-gate-protocol.md`,
      resultsUrl: `${DOCS}/modelkit-gate.md`,
      needed: g.threshold_drugs,
      both: g.drugs_both_tested,
      upperBound: gt.bound.upper_bound_drugs_both,
      interpretable: g.interpretable,
      limitedByData: gt.bound.limiting_factor.startsWith("data"),
      claim: {
        aucDrugs: cc.auc.drugs,
        aucK: cc.auc.within_2_fold,
        aucN: cc.auc.points,
        aucLow: cc.auc.wilson_95[0],
        aucHigh: cc.auc.wilson_95[1],
        cmaxDrugs: cc.cmax.drugs,
      },
      rows: ids.map((id) => ({ id, status: row(id).status })),
      read: {
        k: num("values_read_correctly").k,
        n: num("values_read_correctly").n,
        low: num("values_read_correctly").wilson_95[0],
        high: num("values_read_correctly").wilson_95[1],
        clusterLower: num("values_read_correctly").cluster_lower_95,
      },
      auc: {
        k: num("auc_within_2_fold").k,
        n: num("auc_within_2_fold").n,
        low: num("auc_within_2_fold").wilson_95[0],
        high: num("auc_within_2_fold").wilson_95[1],
        drugs: num("auc_within_2_fold").drugs,
      },
      validated: {
        validated: num("drug_validated").validated,
        total: g.status.validated + g.status.failed + g.status.not_validated,
        withSet: num("drug_validated").with_set,
      },
      documents: {
        pmc: num("document_sources").pmc_tables.estimate,
        pmcLower: num("document_sources").pmc_tables.cluster_lower_95,
        fda: num("document_sources").fda_reviews.estimate,
        fdaLower: num("document_sources").fda_reviews.cluster_lower_95,
      },
      crossStudy: {
        implemented: true,
        switchedOn: x.switched_on,
        ruleMet: x.earlier_verdicts.decision_rule_met,
        wouldWithhold: x.would_withhold,
        checkable: x.checkable,
        confirmed: x.confirmed_values,
      },
    },
  };
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
  const mk = modelkit(root);
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
    modelkitPrecision: mk.precision,
    modelkitGate: mk.gate,
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

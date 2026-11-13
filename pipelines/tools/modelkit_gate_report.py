# ruff: noqa: E501 - commands and report strings
"""Model kit gate report (phase B4): gate bound, gate result, effect of the cross-study plausibility
check, and the "shown / not shown" rows of the research page. Pre-registered in
docs/research/modelkit-gate-protocol.md. Research use only. Not for clinical decisions.

It needs the API's model kit code (set builder, leave-one-study-out validation) and the pipelines'
plausibility check, so it runs in the API environment with the pipelines on the path:

    cd apps/api && PYTHONPATH=../../pipelines uv run python ../../pipelines/tools/modelkit_gate_report.py \\
        --run ../../.data/artifacts/modelkit_evidence/current \\
        --secondary ../../.data/artifacts/modelkit_evidence/runs/20261112T142707Z-8ac5398b-8b3e \\
        --out ../../data/validation/modelkit/gate.json --date 2026-11-13 [--raw FULL_ANALYSIS.json]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

from janus.modelkit.builder import ParameterSet, build_set
from janus.modelkit.evidence import Ev, exclusion_reason, linked_studies, read_run
from janus.modelkit.validate import LABEL_SOURCES, validate, wilson

from janus_pipelines.modelkit.model import DOSE_PARAMS
from janus_pipelines.modelkit.plausibility import (
    FACTOR,
    Obs,
    comparison_key,
    cross_study_outliers,
    normalised,
)
from janus_pipelines.modelkit.units import EXPECTED

THRESHOLD = 10  # drugs with AUC and Cmax tested (DP-M20)
STRICT_TEXT = "both readers agree, but the strict publication check abstained"
WITHHELD_TEXT = (
    "both readers agree, but the value differs more than 10-fold from the drug's other studies "
    "(cross-study check) (more_than_10_fold)"
)
PLAIN = frozenset({"immediate_release", "solution", "unspecified"})


# --- B4.1: bound ---------------------------------------------------------------------------------


def _obs_kind(e: Ev) -> str | None:
    if exclusion_reason(e) or e.origin == "derived" or e.dose is None or e.route != "oral":
        return None
    if e.parameter == "cmax" and (
        e.regimen == "single" or (e.regimen == "multiple" and e.interval_h)
    ):
        return "cmax"
    if e.parameter == "auc_inf" and e.regimen == "single":
        return "auc"
    if e.parameter == "auc_tau" and e.regimen == "multiple" and e.interval_h:
        return "auc"
    return None


def _usable(e: Ev, parameter: str, route: str) -> bool:
    return exclusion_reason(e) is None and e.parameter == parameter and e.route == route


def bound(by: dict[str, list[Ev]]) -> dict[str, Any]:
    tiers: dict[str, dict[str, set[str]]] = {
        t: {"auc": set(), "cmax": set()} for t in ("T0", "T1", "T1b")
    }
    c: Counter[str] = Counter()
    for d, rs in by.items():
        linked = linked_studies(rs)
        obs: dict[tuple[str, str], set[str]] = defaultdict(set)
        for e in rs:
            k = _obs_kind(e)
            if k and e.source_id not in LABEL_SOURCES and e.study not in linked:
                obs[e.study].add(k)
        clear = {e.study for e in rs if _usable(e, "cl_f", "oral") or _usable(e, "cl", "iv")}
        peak = {e.study for e in rs if _usable(e, "tmax", "oral")}
        for s, ks in obs.items():
            for k in ks:
                tiers["T0"][k].add(d)
            if clear - {s}:
                for k in ks:
                    tiers["T1"][k].add(d)
                    if k == "auc" or peak - {s}:
                        tiers["T1b"][k].add(d)
        c["drugs_with_confirmed_value"] += any(e.confirmed for e in rs)
        c["drugs_with_confirmed_values_in_2plus_studies"] += (
            len({e.study for e in rs if e.confirmed}) >= 2
        )
        c["drugs_with_testable_observation"] += bool(obs)
        c["drugs_with_testable_observations_in_2plus_studies"] += len(obs) >= 2
        c["drugs_with_usable_clearance"] += bool(clear)
        c["drugs_with_usable_peak_time"] += bool(peak)
        c["drugs_with_usable_clearance_and_peak_time"] += bool(clear) and bool(peak)
    out: dict[str, Any] = {"counts": dict(sorted(c.items()))}
    for t, m in tiers.items():
        both = sorted(m["auc"] & m["cmax"])
        out[t] = {
            "auc": len(m["auc"]),
            "cmax": len(m["cmax"]),
            "both": len(both),
            "both_drugs": both,
        }
    return out


# --- gate ----------------------------------------------------------------------------------------


def _share(items: list[tuple[str, float]]) -> dict[str, Any] | None:
    if not items:
        return None
    n = len(items)
    k = sum(0.5 <= r <= 2 for _, r in items)
    drugs = sorted({d for d, _ in items})
    rnd = random.Random(20261113)  # noqa: S311 - a seeded bootstrap, not cryptography
    by: dict[str, list[float]] = defaultdict(list)
    for d, r in items:
        by[d].append(r)
    gm: list[float] = []
    for _ in range(2000):
        pool = [r for d in (rnd.choice(drugs) for _ in drugs) for r in by[d]]
        gm.append(math.exp(sum(abs(math.log(r)) for r in pool) / len(pool)))
    gm.sort()
    w = wilson(k, n)
    return {
        "points": n,
        "within_2_fold": k,
        "share": round(k / n, 3),
        "wilson_95": [round(x, 3) for x in w] if w else None,
        "gmfe": round(math.exp(sum(abs(math.log(r)) for _, r in items) / n), 3),
        "gmfe_drug_bootstrap_95": [round(gm[49], 3), round(gm[1949], 3)],
        "drugs": len(drugs),
    }


def gate(by: dict[str, list[Ev]]) -> dict[str, Any]:
    sets = complete = 0
    status: Counter[str] = Counter()
    per: dict[str, dict[str, Any]] = {}
    items: dict[str, list[tuple[str, float]]] = {"auc": [], "cmax": []}
    for d in sorted(by):
        rs = by[d]
        ps = build_set(d, rs)
        v = validate(d, rs, ps)
        if isinstance(ps, ParameterSet):
            sets += 1
            complete += ps.complete
        status[v.status] += 1
        for p in v.points:
            items[p.metric].append((d, p.ratio))
        if v.points or isinstance(ps, ParameterSet):
            per[d] = {
                "set": isinstance(ps, ParameterSet),
                "complete": isinstance(ps, ParameterSet) and ps.complete,
                "status": v.status,
                "auc_points": [round(p.ratio, 3) for p in v.points if p.metric == "auc"],
                "cmax_points": [round(p.ratio, 3) for p in v.points if p.metric == "cmax"],
                "studies": sorted({p.study_id for p in v.points}),
            }
    auc_d = sorted({d for d, _ in items["auc"]})
    cmax_d = sorted({d for d, _ in items["cmax"]})
    both = sorted(set(auc_d) & set(cmax_d))
    drug_ok = [all(0.5 <= r <= 2 for r in per[d]["auc_points"]) for d in auc_d]
    dw = wilson(sum(drug_ok), len(drug_ok))
    return {
        "drugs": len(by),
        "with_set": sets,
        "complete_set": complete,
        "status": dict(sorted(status.items())),
        "drugs_auc_tested": len(auc_d),
        "drugs_cmax_tested": len(cmax_d),
        "drugs_both_tested": len(both),
        "both_tested": both,
        "interpretable": len(both) >= THRESHOLD,
        "auc": _share(items["auc"]),
        "auc_drugs_all_within": {
            "k": sum(drug_ok),
            "n": len(drug_ok),
            "wilson_95": [round(x, 3) for x in dw] if dw else None,
        },
        "cmax": _share(items["cmax"]),
        "studies_auc": len({s for d in auc_d for s in per[d]["studies"]}),
        "per_drug": per,
    }


# --- B4.3: cross-study plausibility on the release rows -------------------------------------------


def plausibility(rows: list[Ev]) -> tuple[list[Ev], list[dict[str, Any]], dict[str, int]]:
    """The rows with the check applied (as the intake would), the withheld values and counts. Rows of
    the ClinicalTrials.gov readers only; derived clearances of a withheld AUC are withheld with it."""
    idx: list[int] = []
    obs: list[Obs] = []
    for i, e in enumerate(rows):
        if e.source_id != "clinicaltrials_gov" or e.origin != "reader_pair":
            continue
        agreed = e.confirmed or e.confirm_reason.startswith(STRICT_TEXT)
        if not agreed or e.analyte_class != "parent":
            continue
        n = normalised(e.parameter, e.value, e.unit, e.dose)
        if n is None:
            continue
        plain = (
            not e.coadministered
            and e.evidence_kind == "pk"
            and "special" not in (e.population or "")
            and e.formulation in PLAIN
        )
        key = comparison_key(e.drug_key, n[0], e.route, e.regimen)
        idx.append(i)
        obs.append(Obs(key, e.study_id, n[1], candidate=e.confirmed, reference=plain))
    flagged = cross_study_outliers(obs)
    summary: dict[tuple[str, ...], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for o in obs:
        if o.reference:
            summary[o.key][o.study].append(math.log(o.value))
    withheld: list[dict[str, Any]] = []
    out = list(rows)
    for j in sorted(flagged):
        e, o = rows[idx[j]], obs[j]
        others = sorted(_median(v) for s, v in summary[o.key].items() if s != o.study)
        ref = math.exp(_median(others))
        withheld.append(
            {
                "drug": e.drug_key,
                "parameter": e.parameter,
                "study": e.study_id,
                "locator": e.source_locator,
                "value": e.value,
                "unit": e.unit,
                "dose_mg": e.dose,
                "route": e.route,
                "regimen": e.regimen,
                "normalised": round(o.value, 6),
                "reference": round(ref, 6),
                "ratio": float(f"{o.value / ref:.3g}"),
                "reference_unit": EXPECTED[o.key[1]][1]
                + (" per mg of dose" if o.key[1] in DOSE_PARAMS else ""),
                "other_studies": len(others),
            }
        )
        out[idx[j]] = replace(e, confirmed=False, confirm_reason=WITHHELD_TEXT)
    gone = {r["locator"] for r in withheld}
    for i, e in enumerate(out):
        if e.origin == "derived" and e.confirmed and e.source_locator.split("#derived-")[0] in gone:
            out[i] = replace(e, confirmed=False, confirm_reason=WITHHELD_TEXT)
    checkable = sum(
        1
        for j, o in enumerate(obs)
        if o.candidate
        and any(oo.reference and oo.key == o.key and oo.study != o.study for oo in obs)
    )
    counts = {
        "candidates": sum(o.candidate for o in obs),
        "checkable": checkable,
        "withheld": len(flagged),
        "derived_withheld": sum(
            1
            for a, b in zip(rows, out, strict=True)
            if a.origin == "derived" and a.confirmed != b.confirmed
        ),
    }
    return out, withheld, counts


def _median(logs: list[float]) -> float:
    s = sorted(logs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _by_drug(rows: list[Ev]) -> dict[str, list[Ev]]:
    by: dict[str, list[Ev]] = defaultdict(list)
    for r in rows:
        by[r.drug_key].append(r)
    return dict(by)


def analyse(run: Path) -> dict[str, Any]:
    manifest, rows = read_run(run)
    by = _by_drug(rows)
    after_rows, withheld, counts = plausibility(rows)
    after_by = _by_drug(after_rows)
    return {
        "run": str(manifest["run_id"]),
        "bound": bound(by),
        "gate": gate(by),
        "plausibility": {
            **counts,
            "by_parameter": dict(Counter(w["parameter"] for w in withheld)),
            "withheld_values": withheld,
            "bound_after": bound(after_by),
            "gate_after": gate(after_by),
        },
    }


def earlier_verdicts(withheld: list[dict[str, Any]], items_csv: Path) -> dict[str, Any]:
    """Earlier automated review verdicts of the withheld values (re-use, not a fresh measurement).
    The public item list names study, drug and parameter, not the cell, so a withheld value is
    matched to every reviewed item of its study, drug and parameter; it counts only when all those
    items carry the same verdict pair."""
    with items_csv.open(encoding="utf-8") as fh:
        items = [r for r in csv.DictReader(fh) if r["source"] == "clinicaltrials_gov"]
    out: list[dict[str, Any]] = []
    for w in withheld:
        m = [
            r
            for r in items
            if (r["study"], r["drug"], r["parameter"]) == (w["study"], w["drug"], w["parameter"])
        ]
        pairs = {(r["verdict_1"], r["verdict_2"]) for r in m}
        out.append(
            {
                "drug": w["drug"],
                "parameter": w["parameter"],
                "study": w["study"],
                "matching_items": len(m),
                "verdicts": sorted("/".join(x) for x in pairs),
            }
        )
    judged = [o for o in out if len(o["verdicts"]) == 1]
    both_correct = sum(o["verdicts"] == ["correct/correct"] for o in judged)
    return {
        "note": "earlier automated review verdicts, re-used; not a fresh measurement",
        "values": out,
        "with_earlier_verdict": len(judged),
        "both_correct": both_correct,
        "decision_rule_met": both_correct * 2 <= len(judged),
    }


def site(
    res: dict[str, Any], precision: dict[str, Any], verdicts: dict[str, Any]
) -> dict[str, Any]:
    """The self-contained file the research page shows (numbers and short English rows)."""
    cur = res["current"]
    g, b, pl = cur["gate"], cur["bound"], cur["plausibility"]
    auc, adr = g["auc"], g["auc_drugs_all_within"]
    ct = precision["sources"]["clinicaltrials_gov"]["shipped"]
    pmc = next(p for p in precision["sources"]["pmc_oa"]["curves"][0]["points"] if p["level"] == 2)
    fda = precision["sources"]["drugsatfda_review"]["curves"][0]["points"][0]
    auc_drugs = sorted(d for d, v in g["per_drug"].items() if v["auc_points"])
    st = g["status"]
    earlier = res.get("secondary")
    met = verdicts["decision_rule_met"]
    claim = (
        f"AUC was within 2-fold of held-out studies in the {auc['drugs']} drugs where it could be "
        f"tested ({auc['within_2_fold']} of {auc['points']} points, Wilson 95 % "
        f"{auc['wilson_95'][0]:.2f}-{auc['wilson_95'][1]:.2f}). Cmax could not be tested for any "
        f"drug. The gate needs {THRESHOLD} drugs with both and has {g['drugs_both_tested']}, so no "
        "statement is made about the model kit as a whole."
    )
    rows = [
        {
            "id": "values_read_correctly",
            "claim": "ClinicalTrials.gov values that pass the strict check are read correctly",
            "status": "proven",
            "detail": f"{ct['k']} of {ct['n']} values correct in a census of {ct['studies']} studies, judged by two automated review passes, not by experts. Covers {ct['coverage_n']} of the {precision['sources']['clinicaltrials_gov']['confirmed_values']:,} values the readers agree on ({round(ct['coverage'] * 100)} %).",
            "numbers": {
                "k": ct["k"],
                "n": ct["n"],
                "estimate": ct["precision"],
                "wilson_95": ct["wilson"],
                "cluster_lower_95": ct["cluster_lower"],
            },
        },
        {
            "id": "auc_within_2_fold",
            "claim": "AUC is predicted within 2-fold for held-out studies",
            "status": "proven",
            "detail": f"Only {auc['drugs']} drugs ({', '.join(auc_drugs)}), {g['studies_auc']} studies. Each point is predicted by a set built without its study. Says nothing about other drugs.",
            "numbers": {
                "k": auc["within_2_fold"],
                "n": auc["points"],
                "estimate": auc["share"],
                "wilson_95": auc["wilson_95"],
                "drugs_all_within": adr["k"],
                "drugs": adr["n"],
                "drugs_wilson_95": adr["wilson_95"],
                "gmfe": auc["gmfe"],
            },
        },
        {
            "id": "cmax_within_2_fold",
            "claim": "Cmax is predicted within 2-fold for held-out studies",
            "status": "not_tested",
            "detail": "No drug has a held-out study with a Cmax and another study with a time of peak concentration, which the set needs for the absorption rate.",
            "numbers": {"drugs_tested": g["drugs_cmax_tested"]},
        },
        {
            "id": "gate",
            "claim": "The model kit is accurate across drugs (the gate)",
            "status": "not_tested",
            "detail": f"The gate is interpretable only with at least {THRESHOLD} drugs that have both AUC and Cmax tested. Today: {g['drugs_both_tested']}. Upper bound with the current data: {b['T1b']['both']}.",
            "numbers": {
                "drugs_both_tested": g["drugs_both_tested"],
                "needed": THRESHOLD,
                "upper_bound": b["T1b"]["both"],
            },
        },
        {
            "id": "drug_validated",
            "claim": "A drug's parameter set is validated (AUC and Cmax both within 2-fold)",
            "status": "not_tested",
            "detail": f"{st.get('validated', 0)} of {g['drugs']} drugs: a drug is validated only when both AUC and Cmax are tested, and no drug has both. {g['with_set']} drugs have a parameter set, {g['complete_set']} of them complete.",
            "numbers": {
                "validated": st.get("validated", 0),
                "failed": st.get("failed", 0),
                "not_validated": st.get("not_validated", 0),
                "with_set": g["with_set"],
            },
        },
        {
            "id": "document_sources",
            "claim": "Values from article tables and FDA review tables are precise enough to publish",
            "status": "not_proven",
            "detail": "Both failed the pre-registered rule (lower 95 % bound at least 0.90) and are held back.",
            "numbers": {
                "pmc_tables": {
                    "estimate": pmc["precision"],
                    "wilson_95": pmc["wilson"],
                    "cluster_lower_95": pmc["cluster_lower"],
                    "n": pmc["n"],
                },
                "fda_reviews": {
                    "estimate": fda["precision"],
                    "wilson_95": fda["wilson"],
                    "cluster_lower_95": fda["cluster_lower"],
                    "n": fda["n"],
                },
            },
        },
        {
            "id": "unit_errors_across_studies",
            "claim": "A value posted with a wrong unit is withheld",
            "status": "proven" if met else "not_proven",
            "detail": "A pre-registered cross-study check withholds the known case (dasatinib clearance posted in mL/h, about 1,000-fold off)"
            + (
                ". It is switched on."
                if met
                else ", but it did not meet its own decision rule and is switched off. Such values can still be shown."
            )
            + " A drug with only one study cannot be checked this way.",
            "numbers": {
                "would_withhold": pl["withheld"],
                "checkable": pl["checkable"],
                "confirmed_values": pl["candidates"],
            },
        },
        {
            "id": "recall",
            "claim": "The readers find every value a source reports",
            "status": "not_tested",
            "detail": "Recall needs experts to annotate whole documents.",
            "numbers": {},
        },
        {
            "id": "special_populations",
            "claim": "Predictions for children, older adults, or kidney or liver impairment",
            "status": "not_tested",
            "detail": "Values from these populations are excluded from building and testing sets.",
            "numbers": {},
        },
        {
            "id": "expert_review",
            "claim": "Experts have checked the values and the method",
            "status": "not_tested",
            "detail": "Expert review has not yet been done.",
            "numbers": {},
        },
    ]
    tiers = [
        ("T0", "usable oral AUC and Cmax observations exist"),
        ("T1", "and another study of the drug has a usable clearance"),
        ("T1b", "and, for Cmax, another study has a time of peak concentration"),
    ]
    return {
        "schema": "modelkit-gate-1",
        "measured_on": res["measured_on"],
        "release": cur["run"],
        "protocol": "docs/research/modelkit-gate-protocol.md",
        "method": "docs/research/modelkit-gate.md",
        "note": "Research use only. Not for clinical decisions. Expert review has not yet been done. Every reading and check is automated.",
        "statuses": {
            "proven": "shown by the data",
            "not_proven": "tested, and not shown",
            "not_tested": "could not be tested yet",
        },
        "gate": {
            "rule": f"interpretable only when at least {THRESHOLD} drugs have both AUC and Cmax tested against held-out studies (leave one study out, 2-fold band)",
            "threshold_drugs": THRESHOLD,
            "drugs_in_release": g["drugs"],
            "drugs_with_set": g["with_set"],
            "complete_sets": g["complete_set"],
            "drugs_auc_tested": g["drugs_auc_tested"],
            "drugs_cmax_tested": g["drugs_cmax_tested"],
            "drugs_both_tested": g["drugs_both_tested"],
            "interpretable": g["interpretable"],
            "status": {
                "validated": st.get("validated", 0),
                "failed": st.get("failed", 0),
                "not_validated": st.get("not_validated", 0),
            },
        },
        "bound": {
            "upper_bound_drugs_both": b["T1b"]["both"],
            "tiers": [
                *(
                    {
                        "id": t,
                        "label": lab,
                        "auc": b[t]["auc"],
                        "cmax": b[t]["cmax"],
                        "both": b[t]["both"],
                    }
                    for t, lab in tiers
                ),
                {
                    "id": "gate",
                    "label": "tested by the product gate",
                    "auc": g["drugs_auc_tested"],
                    "cmax": g["drugs_cmax_tested"],
                    "both": g["drugs_both_tested"],
                },
            ],
            "counts": b["counts"],
            "limiting_factor": "data: too few drugs have a second independent study with a clearance and a time of peak concentration",
            "earlier_release": None
            if earlier is None
            else {
                "release": earlier["run"],
                "note": "before the strict check (every value both readers agree on); its one drug with both metrics tested was dasatinib, through the unit error, and it failed",
                "upper_bound_drugs_both": earlier["bound"]["T1b"]["both"],
                "drugs_both_tested": earlier["gate"]["drugs_both_tested"],
            },
        },
        "claim": {
            "text": claim,
            "auc": {
                "drugs": auc["drugs"],
                "points": auc["points"],
                "within_2_fold": auc["within_2_fold"],
                "wilson_95": auc["wilson_95"],
                "gmfe": auc["gmfe"],
                "gmfe_drug_bootstrap_95": auc["gmfe_drug_bootstrap_95"],
            },
            "cmax": {"drugs": g["drugs_cmax_tested"], "points": 0},
        },
        "cross_study_check": {
            "factor": FACTOR,
            "switched_on": met,
            "confirmed_values": pl["candidates"],
            "checkable": pl["checkable"],
            "would_withhold": pl["withheld"],
            "withheld_values": [
                {
                    k: w[k]
                    for k in (
                        "drug",
                        "parameter",
                        "study",
                        "value",
                        "unit",
                        "reference",
                        "reference_unit",
                        "ratio",
                    )
                }
                for w in pl["withheld_values"]
            ],
            "earlier_verdicts": verdicts,
            "gate_change": pl["gate_after"]["drugs_both_tested"] != g["drugs_both_tested"],
            "decision": "met: switched on"
            if met
            else "not met: the earlier automated review passes judged the withheld values correct (they check the reading against the source, and the source itself carries the unit error), so the check stays switched off",
        },
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--secondary", type=Path)
    ap.add_argument("--raw", type=Path, help="full analysis (private)")
    ap.add_argument("--out", type=Path, required=True, help="the site file (gate.json)")
    ap.add_argument("--date", required=True)
    a = ap.parse_args()
    repo = Path(__file__).resolve().parents[2]
    res: dict[str, Any] = {
        "measured_on": a.date,
        "factor": FACTOR,
        "threshold_drugs_both_tested": THRESHOLD,
        "current": analyse(a.run.resolve()),
    }
    if a.secondary:
        res["secondary"] = analyse(a.secondary.resolve())
    if a.raw:
        a.raw.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    vdir = repo / "data" / "validation" / "modelkit"
    precision = json.loads((vdir / "precision.json").read_text(encoding="utf-8"))
    verdicts = earlier_verdicts(
        res["current"]["plausibility"]["withheld_values"], vdir / "items.csv"
    )
    out = site(res, precision, verdicts)
    a.out.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

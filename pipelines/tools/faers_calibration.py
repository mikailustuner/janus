"""FAERS signal calibration (docs/research/faers-calibration-protocol.md).

Uses Janus's own code paths unchanged: the FAERS name index and resolution ladder
(janus.resolution), the report-level count tables (janus.memory.reader) and the statistics
(janus.memory.stats). Standard library only otherwise. Runs in the API environment:

    cd apps/api && uv run python ../../pipelines/tools/faers_calibration.py \
        --data-dir ../../.data --ref ../../data/validation/faers \
        --out ../../data/validation/faers/results
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

OUTCOMES: dict[str, list[str]] = {
    "acute_liver_injury": [
        "Acute hepatic failure", "Hepatic failure", "Liver injury", "Drug-induced liver injury",
        "Hepatitis acute", "Hepatitis fulminant", "Hepatotoxicity", "Hepatocellular injury",
        "Cholestatic liver injury", "Mixed liver injury", "Hepatic necrosis",
    ],
    "acute_kidney_injury": [
        "Acute kidney injury", "Renal failure", "Renal failure acute", "Renal injury",
        "Nephropathy toxic", "Renal tubular necrosis", "Tubulointerstitial nephritis", "Anuria",
    ],
    "acute_myocardial_infarction": [
        "Acute myocardial infarction", "Myocardial infarction", "Silent myocardial infarction",
    ],
    "upper_gi_bleeding": [
        "Upper gastrointestinal haemorrhage", "Gastric haemorrhage", "Duodenal ulcer haemorrhage",
        "Gastric ulcer haemorrhage", "Peptic ulcer haemorrhage", "Haematemesis", "Melaena",
        "Oesophageal haemorrhage", "Gastritis haemorrhagic",
    ],
    "anaphylaxis": [
        "Anaphylactic reaction", "Anaphylactic shock", "Anaphylactoid reaction",
        "Anaphylactoid shock",
    ],
    "aplastic_anaemia": ["Aplastic anaemia", "Bone marrow failure", "Pancytopenia"],
    "cardiac_valve_fibrosis": [
        "Cardiac valve fibrosis", "Cardiac valve disease", "Mitral valve incompetence",
        "Aortic valve incompetence", "Tricuspid valve incompetence",
    ],
    "leukopenia": [
        "Leukopenia", "Neutropenia", "Agranulocytosis", "Febrile neutropenia",
        "White blood cell count decreased", "Neutrophil count decreased",
    ],
    "rhabdomyolysis": ["Rhabdomyolysis", "Myoglobinuria", "Necrotising myositis"],
    "stevens_johnson": [
        "Stevens-Johnson syndrome", "Toxic epidermal necrolysis", "SJS-TEN overlap",
    ],
}  # fmt: skip

OUTCOME_OF = {
    "OMOP Acute Liver Failure 1": "acute_liver_injury",
    "OMOP Acute Renal Failure 1": "acute_kidney_injury",
    "OMOP Acute myocardial Infarction  1": "acute_myocardial_infarction",
    "HOI Upper GI #3": "upper_gi_bleeding",
    "Anaphylaxis #1": "anaphylaxis",
    "OMOP Aplastic Anemia 1": "aplastic_anaemia",
    "Cardiac Valve Fibrosis #1": "cardiac_valve_fibrosis",
    "Leukopenia Including Neutropenia and Agranulocytosis": "leukopenia",
    "Rhabdomyolysis #1": "rhabdomyolysis",
    "Stevens-Johnson Syndrome #1": "stevens_johnson",
}
Z95 = 1.959964


# --- statistics (stdlib) -------------------------------------------------------------------


def wilson(k: int, n: int) -> dict[str, Any]:
    if n == 0:
        return {"k": 0, "n": 0, "estimate": None, "ci95_low": None, "ci95_high": None}
    p = k / n
    d = 1 + Z95**2 / n
    c = (p + Z95**2 / (2 * n)) / d
    h = Z95 * math.sqrt(p * (1 - p) / n + Z95**2 / (4 * n * n)) / d
    return {
        "k": k,
        "n": n,
        "estimate": p,
        "ci95_low": max(0.0, c - h),
        "ci95_high": min(1.0, c + h),
    }


def auc_delong(pos: list[float], neg: list[float]) -> dict[str, Any]:
    """AUC with the DeLong variance (DeLong et al., Biometrics 1988)."""
    m, n = len(pos), len(neg)
    if m < 2 or n < 2:
        return {"auc": None, "ci95_low": None, "ci95_high": None, "n_pos": m, "n_neg": n}

    def psi(x: float, y: float) -> float:
        return 1.0 if x > y else 0.5 if x == y else 0.0

    v10 = [sum(psi(x, y) for y in neg) / n for x in pos]
    v01 = [sum(psi(x, y) for x in pos) / m for y in neg]
    auc = sum(v10) / m
    s10 = sum((v - auc) ** 2 for v in v10) / (m - 1)
    s01 = sum((v - auc) ** 2 for v in v01) / (n - 1)
    se = math.sqrt(s10 / m + s01 / n)
    return {
        "auc": auc,
        "se": se,
        "ci95_low": max(0.0, auc - Z95 * se),
        "ci95_high": min(1.0, auc + Z95 * se),
        "n_pos": m,
        "n_neg": n,
    }


def norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def fit_null(est: list[tuple[float, float]]) -> tuple[float, float]:
    """ML fit of N(mu, sigma^2) systematic error to (ln estimate, se) pairs (Schuemie 2014).

    For fixed sigma the MLE of mu is the inverse-variance weighted mean; sigma maximises the
    profile likelihood (golden-section search on [0, 5])."""

    def mu_of(s: float) -> float:
        w = [1 / (s * s + se * se) for _, se in est]
        return sum(wi * x for wi, (x, _) in zip(w, est, strict=True)) / sum(w)

    def loglik(s: float) -> float:
        mu = mu_of(s)
        return -0.5 * sum(
            math.log(s * s + se * se) + (x - mu) ** 2 / (s * s + se * se) for x, se in est
        )

    lo, hi = 0.0, 5.0
    g = (math.sqrt(5) - 1) / 2
    a, b = hi - g * (hi - lo), lo + g * (hi - lo)
    for _ in range(200):
        if loglik(a) > loglik(b):
            hi = b
        else:
            lo = a
        a, b = hi - g * (hi - lo), lo + g * (hi - lo)
    s = (lo + hi) / 2
    return mu_of(s), s


def calibrated_p(x: float, se: float, mu: float, sigma: float) -> float:
    z = (x - mu) / math.sqrt(sigma * sigma + se * se)
    return 2 * norm_sf(abs(z))


# --- inputs --------------------------------------------------------------------------------


def reference(ref_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    for fname, set_name in (
        ("omop_reference_set.csv", "omop"),
        ("euadr_reference_set.csv", "euadr"),
    ):
        with (ref_dir / fname).open(newline="") as f:
            for r in csv.DictReader(f):
                key = (r["exposureName"].strip().casefold(), OUTCOME_OF[r["outcomeName"]])
                truth = int(float(r["groundTruth"]))
                if key in seen:
                    if seen[key]["truth"] != truth:
                        conflicts.append({"drug": key[0], "outcome": key[1]})
                        seen[key]["conflict"] = True
                    else:
                        seen[key]["sets"].append(set_name)
                    continue
                seen[key] = {
                    "drug": r["exposureName"].strip(),
                    "outcome": key[1],
                    "truth": truth,
                    "sets": [set_name],
                }
    pairs = [p for p in seen.values() if not p.get("conflict")]
    return pairs, conflicts


def name_index(data_dir: Path) -> Any:
    from janus.resolution import load as resolution_load
    from janus.resolution.prepare import build_name_index

    inputs = resolution_load.gather(data_dir)
    for a in inputs.artifacts.values():
        a.verify()
    wikidata = inputs.artifacts[resolution_load.WIKIDATA].rows
    return build_name_index(
        wikidata,
        inputs.rules,
        inputs.synonyms,
        inputs.curated.rows,
        inputs.acid,
        frozenset(c.key for c in inputs.component_codes),
        inputs.code_exclusions,
    )


# --- main ----------------------------------------------------------------------------------


def ln_ror_haldane(a: int, b: int, c: int, d: int) -> tuple[float, float]:
    if 0 in (a, b, c, d):
        a, b, c, d = (x + 0.5 for x in (a, b, c, d))  # type: ignore[assignment]
    return math.log(a * d / (b * c)), math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)


def svg_plot(rows: list[dict[str, Any]], mu: float, sigma: float) -> str:
    """Estimate against standard error (0 at the bottom) with the fitted null's 95 % band."""
    w, h, left, right, top, bottom = 680, 440, 64, 24, 48, 56
    x0, x1 = math.log(0.01), math.log(1000.0)
    y1 = 2.5

    def px(x: float) -> float:
        x = min(max(x, x0), x1)
        return left + (x - x0) / (x1 - x0) * (w - left - right)

    def py(y: float) -> float:
        y = min(y, y1)
        return h - bottom - y / y1 * (h - top - bottom)

    font = 'font-family="sans-serif" fill="#1f2933"'
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" '
        'aria-label="FAERS reporting odds ratios of the reference pairs against their standard '
        'error, with the 95 % band of the fitted distribution for pairs without an effect">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
    ]
    steps = [y1 * k / 50 for k in range(51)]
    right_edge = [(px(mu + Z95 * math.sqrt(sigma**2 + se**2)), py(se)) for se in steps]
    left_edge = [(px(mu - Z95 * math.sqrt(sigma**2 + se**2)), py(se)) for se in reversed(steps)]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in right_edge + left_edge)
    out.append(f'<polygon points="{pts}" fill="#d9e2ec" stroke="none"/>')
    for ratio in (0.01, 0.1, 1, 10, 100, 1000):
        x = px(math.log(ratio))
        out.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{h - bottom}" '
            f'stroke="{"#52606d" if ratio == 1 else "#e4e7eb"}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{x:.1f}" y="{h - bottom + 18}" text-anchor="middle" font-size="12" {font}>'
            f"{ratio:g}</text>"
        )
    for se in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5):
        y = py(se)
        out.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="12" {font}>'
            f"{se:g}</text>"
        )
    out.append(
        f'<line x1="{left}" y1="{h - bottom}" x2="{w - right}" y2="{h - bottom}" stroke="#52606d"/>'
    )
    for truth, color in ((0, "#1d4ed8"), (1, "#c2410c")):
        for r in rows:
            if r["truth"] == truth:
                out.append(
                    f'<circle cx="{px(r["ln_ror"]):.1f}" cy="{py(r["se"]):.1f}" r="3" '
                    f'fill="{color}" fill-opacity="0.65"/>'
                )
    out.append(
        f'<text x="{(left + w - right) / 2}" y="{h - 14}" text-anchor="middle" font-size="13" '
        f"{font}>Reporting odds ratio (log scale)</text>"
    )
    out.append(
        f'<text x="18" y="{(top + h - bottom) / 2}" font-size="13" {font} text-anchor="middle" '
        f'transform="rotate(-90 18 {(top + h - bottom) / 2})">Standard error of ln ROR</text>'
    )
    legend = [
        ("#c2410c", "circle", "Positive control"),
        ("#1d4ed8", "circle", "Negative control"),
        ("#d9e2ec", "rect", "95 % range without an effect (fitted)"),
    ]
    lx = left
    for color, kind, label in legend:
        if kind == "circle":
            out.append(f'<circle cx="{lx + 6}" cy="22" r="5" fill="{color}"/>')
        else:
            out.append(f'<rect x="{lx}" y="16" width="12" height="12" fill="{color}"/>')
        out.append(f'<text x="{lx + 18}" y="26" font-size="12" {font}>{label}</text>')
        lx += 18 + 7 * len(label) + 24
    out.append("</svg>")
    return "\n".join(out)


def analyse(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Every number of the results from the 2x2 tables (no FAERS access needed)."""
    est = [r for r in rows if r["estimable"]]
    pos = [r["ln_ror"] for r in est if r["truth"] == 1]
    neg = [r["ln_ror"] for r in est if r["truth"] == 0]
    low = min((r["ln_ror"] for r in est), default=0.0) - 1
    all_pos = [r["ln_ror"] if r["estimable"] else low for r in rows if r["truth"] == 1]
    all_neg = [r["ln_ror"] if r["estimable"] else low for r in rows if r["truth"] == 0]

    by_set: dict[str, Any] = {}
    for s in ("omop", "euadr"):
        sub = [r for r in est if s in r["sets"]]
        by_set[s] = auc_delong(
            [r["ln_ror"] for r in sub if r["truth"]], [r["ln_ror"] for r in sub if not r["truth"]]
        )
    by_outcome = {
        o: auc_delong(
            [r["ln_ror"] for r in est if r["outcome"] == o and r["truth"]],
            [r["ln_ror"] for r in est if r["outcome"] == o and not r["truth"]],
        )
        for o in OUTCOMES
    }

    tp = sum(1 for r in est if r["truth"] and r["evans_met"])
    tn = sum(1 for r in est if not r["truth"] and not r["evans_met"])
    n_pos, n_neg = len(pos), len(neg)

    negs = [(r["ln_ror"], r["se"]) for r in est if not r["truth"]]
    mu, sigma = fit_null(negs)
    nominal_excl = sum(1 for x, se in negs if abs(x) > Z95 * se)
    loo_excl = 0
    for i, (x, se) in enumerate(negs):
        m_i, s_i = fit_null(negs[:i] + negs[i + 1 :])
        loo_excl += calibrated_p(x, se, m_i, s_i) < 0.05
    for r in est:
        r["p_nominal"] = 2 * norm_sf(abs(r["ln_ror"]) / r["se"])
        r["p_calibrated"] = calibrated_p(r["ln_ror"], r["se"], mu, sigma)
    pos_cal = [r for r in est if r["truth"]]

    reasons: dict[str, int] = {}
    for r in rows:
        if not r["estimable"]:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1

    return {
        "pairs": {
            "total": len(rows),
            "positive": sum(r["truth"] for r in rows),
            "negative": sum(1 - r["truth"] for r in rows),
            "estimable": len(est),
            "not_estimable_by_reason": reasons,
        },
        "primary_auc_ln_ror": auc_delong(pos, neg),
        "secondary": {
            "auc_including_not_estimable_at_lowest_score": auc_delong(all_pos, all_neg),
            "auc_by_set": by_set,
            "auc_by_outcome": by_outcome,
            "evans_sensitivity": wilson(tp, n_pos),
            "evans_specificity": wilson(tn, n_neg),
            "empirical_null": {"mean_ln": mu, "sd_ln": sigma, "n_negative_controls": len(negs)},
            "negatives_ci_excluding_1_nominal": wilson(nominal_excl, len(negs)),
            "negatives_p_below_005_calibrated_leave_one_out": wilson(loo_excl, len(negs)),
            "positives_p_below_005_nominal": wilson(
                sum(r["p_nominal"] < 0.05 for r in pos_cal), len(pos_cal)
            ),
            "positives_p_below_005_calibrated": wilson(
                sum(r["p_calibrated"] < 0.05 for r in pos_cal), len(pos_cal)
            ),
        },
    }


def verify(out: Path) -> int:
    """Recompute every number from the committed tables (pairs.csv) and compare with metrics.json.

    Needs no FAERS data, so CI can run it (docs/research/reproduce.md)."""
    with (out / "pairs.csv").open(newline="") as f:
        rows: list[dict[str, Any]] = []
        for r in csv.DictReader(f):
            rec: dict[str, Any] = {
                **r,
                "truth": int(r["truth"]),
                "estimable": r["estimable"] == "True",
            }
            if rec["estimable"]:
                rec.update(
                    ln_ror=float(r["ln_ror"]), se=float(r["se"]), evans_met=r["evans_met"] == "True"
                )
            rows.append(rec)
    got = json.loads(json.dumps(analyse(rows)))
    want = json.loads((out / "metrics.json").read_text())
    want["pairs"].pop(
        "conflicting_labels_dropped", None
    )  # a property of the inputs, not the tables
    bad = [k for k in got if not _close(got[k], want.get(k))]
    print("faers calibration: " + ("reproduced" if not bad else f"differs in {bad}"))
    return 1 if bad else 0


def _close(a: Any, b: Any) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k]) for k in a)
    if isinstance(a, float) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return a == b


def main() -> None:
    from janus.memory.faers_build import counts_root, current_build
    from janus.memory.reader import ALL_REGION, CountsReader, Session
    from janus.memory.stats import cells_from_counts, evaluate
    from janus.resolution.matching import map_name

    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--ref", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    pairs, conflicts = reference(args.ref)
    index = name_index(args.data_dir)
    build = current_build(args.data_dir)
    if build is None:
        raise SystemExit("no FAERS counts build under the data directory")
    reader = CountsReader(counts_root(args.data_dir) / "current" / "faers_counts.duckdb")
    session = Session(reader)
    all_pts = [
        str(r[0])
        for r in reader._con.execute(  # pyright: ignore[reportPrivateUsage]
            "SELECT DISTINCT pt FROM faers_report_event"
        ).fetchall()
    ]
    by_fold: dict[str, list[str]] = {}
    for pt in all_pts:
        by_fold.setdefault(pt.casefold(), []).append(pt)
    outcome_pts = {
        o: sorted({p for t in terms for p in by_fold.get(t.casefold(), [])})
        for o, terms in OUTCOMES.items()
    }
    missing_terms = {
        o: [t for t in terms if t.casefold() not in by_fold] for o, terms in OUTCOMES.items()
    }

    rows: list[dict[str, Any]] = []
    for p in pairs:
        m = map_name(p["drug"].upper(), index, lang="en")
        rec = {**p, "sets": "+".join(p["sets"]), "map_status": m.status}
        if m.status != "mapped":
            rec["estimable"] = False
            rec["reason"] = "name_not_mapped"
            rows.append(rec)
            continue
        key = m.keys[0]
        raw = session.cells([key], outcome_pts[p["outcome"]], "suspect", [ALL_REGION])[ALL_REGION]
        table = cells_from_counts(raw.a, raw.exposure, raw.event_mapped, raw.n_mapped)
        st = evaluate(table)
        rec.update(
            key=key,
            a=table.a,
            b=table.b,
            c=table.c,
            d=table.d,
            assessment=st.assessment,
            evans_met=st.evans_met,
            ror=st.estimates.ror if st.estimates else None,
            ror_ci_low=st.estimates.ror_ci.low if st.estimates else None,
            ror_ci_high=st.estimates.ror_ci.high if st.estimates else None,
            prr=st.estimates.prr if st.estimates else None,
        )
        if raw.exposure == 0:
            rec["estimable"] = False
            rec["reason"] = "no_reports_for_drug"
        else:
            rec["estimable"] = True
            rec["ln_ror"], rec["se"] = ln_ror_haldane(table.a, table.b, table.c, table.d)
        rows.append(rec)

    analysis = analyse(rows)
    est = [r for r in rows if r["estimable"]]
    mu = analysis["secondary"]["empirical_null"]["mean_ln"]
    sigma = analysis["secondary"]["empirical_null"]["sd_ln"]
    p = analysis["pairs"]
    metrics = {
        "faers_counts_build": build,
        "faers_run_id": reader.meta.get("faers_run_id") if isinstance(reader.meta, dict) else None,
        "pairs": {
            "total": p["total"],
            "positive": p["positive"],
            "negative": p["negative"],
            "conflicting_labels_dropped": conflicts,
            "estimable": p["estimable"],
            "not_estimable_by_reason": p["not_estimable_by_reason"],
        },
        "primary_auc_ln_ror": analysis["primary_auc_ln_ror"],
        "secondary": analysis["secondary"],
        "outcome_terms_found": outcome_pts,
        "outcome_terms_not_in_faers": missing_terms,
        "note_a0": "Pairs with a = 0 have no estimate in Janus; their AUC score is ln ROR with "
        "0.5 added to every cell (the Haldane rule Janus applies to zero cells).",
    }
    fields = [
        "drug", "outcome", "truth", "sets", "map_status", "key", "estimable", "reason",
        "a", "b", "c", "d", "ror", "ror_ci_low", "ror_ci_high", "prr", "evans_met", "assessment",
        "ln_ror", "se", "p_nominal", "p_calibrated",
    ]  # fmt: skip
    with (args.out / "pairs.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["outcome"], r["drug"].casefold())):
            w.writerow(r)
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=1, default=str) + "\n")
    (args.out / "calibration.svg").write_text(svg_plot(est, mu, sigma) + "\n")
    print(json.dumps({k: metrics[k] for k in ("pairs", "primary_auc_ln_ror")}, indent=1))


if __name__ == "__main__":
    import sys

    if sys.argv[1:2] == ["--verify"]:
        raise SystemExit(verify(Path(sys.argv[2])))
    main()

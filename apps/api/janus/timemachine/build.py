"""Offline build: pipeline artifacts + curated tables → the files the API serves
(time-machine design §8, Req 8). Run with

    python -m janus.timemachine.build

Nothing here runs on a request. Writes `<JANUS_DATA_DIR>/timemachine/<run>/` and moves the
`current` symlink. Every number carries its source; a model that failed validation can never
carry an exposure statement (Req 5.4).
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from janus.timemachine.exposure import compare
from janus.timemachine.onset import MIN_REPORTS, OnsetSummary, summarize
from janus.timemachine.pk import (
    Band,
    LogNormal,
    OneCompartment,
    ParamSpec,
    Uniform,
    auc_inf,
    cmax,
    mg_per_l_to_um,
    simulate,
    tmax,
)
from janus.timemachine.twin import (
    Published,
    PublishedKind,
    agreement,
    onset_curve,
    risk_window,
)
from janus.timemachine.units import load_units, to_grams
from janus.timemachine.validation import DrugValidation, summary

SEED = 20261109
SIM_N = 2000
CURVE_HOURS = [0.25 * i for i in range(0, 193)]  # 0-48 h
ONSET_GRID = [float(d) for d in (0, 7, 14, 21, 28, 45, 60, 90, 120, 180, 270, 365)]
SMALL_SAMPLE = 30


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def data_dir() -> Path:
    value = os.environ.get("JANUS_DATA_DIR", "").strip()
    return Path(value) if value else repo_root() / ".data"


def _curated(name: str) -> list[dict[str, str]]:
    with (repo_root() / "data" / "time_machine" / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _artifact(name: str) -> Path:
    path = data_dir() / "artifacts" / name / "current"
    if not path.exists():
        raise FileNotFoundError(f"no current {name} run; run the pipeline first")
    return path.resolve()


def _manifest(name: str) -> dict[str, Any]:
    return json.loads((_artifact(name) / "manifest.json").read_text())


def _query(sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    rel = duckdb.sql(sql)
    if rel is None:  # a statement that returns nothing; never used here
        raise ValueError("query returned no relation")
    return list(rel.columns), rel.fetchall()


def _rows(name: str) -> list[dict[str, Any]]:
    path = _artifact(name) / "rows.parquet"
    cols, data = _query(f"select * from read_parquet('{path}')")  # noqa: S608 - our own path
    return [dict(zip(cols, r, strict=True)) for r in data]


# --- validation ------------------------------------------------------------------------------


def validation_rows() -> tuple[list[DrugValidation], list[DrugValidation]]:
    """(PBPK validation, compartmental validation). Observed values come from
    `observed_pk.csv`; predictions from the `tm_pbpk` artifact and from the compartmental
    parameters."""
    observed = {r["drug"]: r for r in _curated("observed_pk.csv")}
    pbpk = [r for r in _rows("tm_pbpk") if r["kind"] == "validation"]
    out: list[DrugValidation] = []
    for r in pbpk:
        drug = str(r["drug"]).lower()
        obs = observed.get(drug)
        if obs is None:
            continue
        out.append(
            DrugValidation(
                drug=drug,
                reference=obs["reference_key"],
                observed_cmax=float(obs["cmax_ng_ml"]),
                observed_auc=float(obs["auc_ng_h_ml"]),
                predicted_cmax=float(r["cmax_ng_ml"]),
                predicted_auc=float(r["auc_ng_h_ml"]),
                note=f"httk PBPK, observed AUC kind {obs['auc_kind']}",
            )
        )
    comp: list[DrugValidation] = []
    for spec in _curated("compartmental_pk.csv"):
        drug = spec["drug"]
        obs = observed.get(drug)
        if obs is None:
            continue
        m = model_for(spec)
        dose = float(obs["dose_mg"])
        comp.append(
            DrugValidation(
                drug=drug,
                reference=obs["reference_key"],
                observed_cmax=float(obs["cmax_ng_ml"]),
                observed_auc=float(obs["auc_ng_h_ml"]),
                predicted_cmax=cmax(m, dose) * 1000.0,
                predicted_auc=auc_inf(m, dose) * 1000.0,
                note=(
                    "minimal compartmental model with cited parameters, not PBPK; AUC is F*D/CL "
                    "by construction, so only Cmax and Tmax are independent of the parameter "
                    f"sources; observed AUC kind {obs['auc_kind']}"
                ),
            )
        )
    return out, comp


def model_for(spec: Mapping[str, str]) -> OneCompartment:
    return OneCompartment(
        f=float(spec["f"]),
        ka=float(spec["ka_per_h"]),
        cl=float(spec["cl_l_per_h"]),
        v=float(spec["v_l"]),
        tlag=float(spec["tlag_h"]),
    )


def spec_for(spec: Mapping[str, str]) -> ParamSpec:
    return ParamSpec(
        f=Uniform(float(spec["f"]) * 0.8, min(float(spec["f"]) * 1.2, 1.0)),
        ka=LogNormal(float(spec["ka_per_h"]), float(spec["ka_gsd"])),
        cl=LogNormal(float(spec["cl_l_per_h"]), float(spec["cl_gsd"])),
        v=LogNormal(float(spec["v_l"]), float(spec["v_gsd"])),
        tlag=Uniform(0.0, float(spec["tlag_h"]) * 2),
    )


# --- L1/L2: substances, constituents, targets ------------------------------------------------


def interaction_flags() -> dict[str, list[dict[str, Any]]]:
    """Pharmacokinetic-interaction flags found by the pipeline. The measured values sit in
    ChEMBL-deposited PubChem records (CC BY-SA 3.0) and are therefore not stored: the flag
    carries the assay id, the target and the evidence reference, never the number (DP-T5)."""
    pointers = _manifest("tm_bioactivity")["metrics"]["pk_interaction_pointers"]
    # Established interactions are curated per (compound, target) with their own evidence.
    # Everything else is a screening-panel record: a signal to check, never an established fact.
    established = {("hyperforin", "NR1I2 (PXR)"): "moore_2000_pxr"}
    out: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str]] = set()
    for p in pointers:
        key = (str(p["compound"]), str(p["gene"]))
        if key in seen:
            continue
        seen.add(key)
        out.setdefault(str(p["compound"]), []).append(
            {
                "gene": p["gene"],
                "entrez_gene": p["entrez_gene"],
                "measure": p["activity_name"],
                "pubchem_aid": p["aid"],
                "value_withheld_licence": p["licence_class"],
                "evidence_reference_key": established.get(key),
                "established": key in established,
                "meaning": "an established interaction with cited evidence"
                if key in established
                else "a record of activity on a drug-metabolism target in a screening panel: "
                "a signal to check, not an established interaction",
            }
        )
    return out


def substance_cards() -> list[dict[str, Any]]:
    molecules = _rows("tm_molecules")
    admet = {str(r["name"]): r for r in _rows("tm_admet")}
    bio = _rows("tm_bioactivity")
    constituents = _curated("constituents.csv")
    flags = interaction_flags()
    labels = _rows("tm_labels")
    comparators = _curated("comparators.csv")
    occ = {
        (str(r["substance_id"]), str(r["compound"])): r
        for r in molecules
        if r["kind"] == "occurrence"
    }
    by_substance: dict[str, list[dict[str, Any]]] = {}
    for c in constituents:
        key = (c["substance_id"], c["compound"])
        row = occ.get(key)
        if row is None:
            continue
        a = admet.get(c["compound"], {})
        acts = [
            {
                "gene": b["entrez_gene"],
                "target": b["target_accession"],
                "measure": b["activity_name"],
                "value_um": b["value_um"],
                "outcome": b["outcome"],
                "assay": b["assay_name"],
                "depositor": b["depositor"],
                "aid": b["aid"],
            }
            for b in bio
            if str(b["compound"]) == c["compound"] and b["outcome"] == "Active"
        ]
        acts.sort(key=lambda x: float(x["value_um"] or 0.0))
        by_substance.setdefault(c["substance_id"], []).append(
            {
                "compound": c["compound"],
                "pubchem_cid": c["pubchem_cid"],
                "inchikey": c["inchikey"],
                "wikidata_qid": row["wikidata_qid"],
                "taxon_qids": list(row["taxon_qids"] or []),
                "occurrence_reference_qids": list(row["reference_qids"] or []),
                "why_selected": c["why"],
                "molecular_weight": a.get("molecular_weight"),
                "admet": {
                    k: a.get(k)
                    for k in (
                        "Half_Life_Obach",
                        "VDss_Lombardo",
                        "PPBR_AZ",
                        "Bioavailability_Ma",
                        "HIA_Hou",
                        "CYP3A4_Veith",
                        "hERG",
                        "DILI",
                    )
                },
                "measured_activities": acts[:12],
                "measured_activity_count": len(acts),
                "interaction_flags": flags.get(c["compound"], []),
            }
        )
    label_by_drug = {str(r["drug"]): r for r in labels}
    cards: list[dict[str, Any]] = []
    for substance_id, items in sorted(by_substance.items()):
        drugs = [
            {
                "drug": c["drug"],
                "condition_key": c["condition_key"],
                "indication_term": label_by_drug.get(c["drug"], {}).get("term"),
                "label_set_id": label_by_drug.get(c["drug"], {}).get("set_id"),
                "label_effective_time": label_by_drug.get(c["drug"], {}).get("effective_time"),
                "bridge_note": c["why"],
            }
            for c in comparators
            if c["substance_id"] == substance_id
        ]
        cards.append({"substance_id": substance_id, "constituents": items, "todays_drugs": drugs})
    return cards


# --- L4: exposure vs potency ------------------------------------------------------------------


@dataclass(frozen=True)
class DoseScenario:
    substance_id: str
    amount: float
    unit: str
    content_low: float
    content_high: float
    constituent: str
    reference_keys: str
    note: str


def dose_scenarios() -> list[DoseScenario]:
    return [
        DoseScenario(
            substance_id=r["substance_id"],
            amount=float(r["amount"]),
            unit=r["unit"],
            content_low=float(r["content_low_percent"]),
            content_high=float(r["content_high_percent"]),
            constituent=r["constituent"],
            reference_keys=r["reference_keys"],
            note=r["note"],
        )
        for r in _curated("dose_scenarios.csv")
    ]


def exposure_cards(credible: Mapping[str, bool]) -> list[dict[str, Any]]:
    units = load_units(repo_root() / "data" / "time_machine" / "units.csv")
    specs = {r["drug"]: r for r in _curated("compartmental_pk.csv")}
    admet = {str(r["name"]): r for r in _rows("tm_admet")}
    bio = _rows("tm_bioactivity")
    out: list[dict[str, Any]] = []
    for s in dose_scenarios():
        grams = to_grams(s.amount, s.unit, units)
        mg_low = grams.low * 1000 * s.content_low / 100
        mg_high = grams.high * 1000 * s.content_high / 100
        spec = specs.get(s.constituent)
        card: dict[str, Any] = {
            "substance_id": s.substance_id,
            "constituent": s.constituent,
            "historical_dose": {
                "amount": s.amount,
                "unit": s.unit,
                "grams_low": grams.low,
                "grams_central": grams.central,
                "grams_high": grams.high,
                "unit_sources": list(units[s.unit].sources),
            },
            "constituent_dose_mg": {"low": mg_low, "high": mg_high},
            "content_percent": {"low": s.content_low, "high": s.content_high},
            "reference_keys": s.reference_keys.split("|"),
            "note": s.note,
            "model": None,
            "comparison": None,
            "model_validated": False,
            "not_validated_reason": "no published human PK parameters for this constituent",
        }
        if spec is not None:
            rng = random.Random(SEED)
            peaks = simulate(spec_for(spec), (mg_low + mg_high) / 2, CURVE_HOURS, rng, n=SIM_N)
            mw = admet.get(s.constituent, {}).get("molecular_weight")
            card["model"] = {
                "kind": "compartmental",
                "label": "minimal compartmental model with cited physiological parameters "
                "(not PBPK)",
                "peak_mg_per_l": {"p5": peaks[1].p5, "p50": peaks[1].p50, "p95": peaks[1].p95},
                "tmax_h": tmax(model_for(spec)),
                "parameter_sources": spec["reference_keys"].split("|"),
            }
            card["model_validated"] = bool(credible.get(s.constituent))
            card["not_validated_reason"] = (
                "" if card["model_validated"] else "model failed the credibility rule for this drug"
            )
            # Only a curated, condition-relevant target may carry a verdict: the most
            # sensitive assay in PubChem is usually an unrelated screen (DP-T13).
            relevant = {
                t["entrez_gene"]
                for t in _curated("potency_targets.csv")
                if t["constituent"] == s.constituent
            }
            potencies = [
                b
                for b in bio
                if str(b["compound"]) == s.constituent
                and b["outcome"] == "Active"
                and b["value_um"] is not None
                and str(b["entrez_gene"]) in relevant
            ]
            card["curated_targets"] = sorted(relevant)
            if not potencies:
                card["no_potency_reason"] = (
                    "no measured potency on a curated, condition-relevant target from a "
                    "public-domain depositor; a recorded gap, not a substituted value"
                )
            if potencies and mw and card["model_validated"]:
                best = min(potencies, key=lambda b: float(b["value_um"]))
                peak_um = Band(
                    mg_per_l_to_um(peaks[1].p5, float(mw)),
                    mg_per_l_to_um(peaks[1].p50, float(mw)),
                    mg_per_l_to_um(peaks[1].p95, float(mw)),
                )
                # PPBR_AZ is a *predicted* percent bound and is not constrained to 0-100: it
                # comes out above 100 for several constituents. An out-of-range prediction
                # gives no usable unbound fraction, so the comparison falls back to the total
                # concentration (an upper bound on exposure) instead of a negative fraction.
                fu = admet.get(s.constituent, {}).get("PPBR_AZ")
                unbound: float | None = None
                if fu is not None and 0.0 <= float(fu) < 100.0:
                    unbound = 1 - float(fu) / 100
                cmp_ = compare(peak_um, float(best["value_um"]), unbound)
                card["comparison"] = {
                    "verdict": cmp_.verdict.value,
                    "basis": cmp_.basis.value,
                    "margin_low": cmp_.margin_low,
                    "margin_high": cmp_.margin_high,
                    "potency_um": best["value_um"],
                    "potency_measure": best["activity_name"],
                    "potency_assay": best["assay_name"],
                    "potency_aid": best["aid"],
                    "unbound_fraction_source": "ADMET-AI PPBR_AZ prediction, not a measurement"
                    if unbound is not None
                    else "no usable unbound fraction (the predicted percent bound is outside "
                    "0-100); compared on the total concentration",
                }
        out.append(card)
    return out


# --- the digital twin ------------------------------------------------------------------------


def onset_days(ingredients: Sequence[str], pts: Sequence[str]) -> list[float]:
    onset = _artifact("faers_onset") / "rows.parquet"
    reports = _artifact("faers") / "rows.parquet"
    il = ", ".join(f"'{i}'" for i in ingredients)
    pl = ", ".join(f"'{p}'" for p in pts)
    q = f"""
    with o as (
      select primaryid, onset_days,
             list_transform(ingredients, lambda x: split_part(upper(x), ' ', 1)) ing
      from read_parquet('{onset}') where role in ('PS', 'SS')
    ), r as (select primaryid, events from read_parquet('{reports}'))
    select min(o.onset_days)
    from o join r using (primaryid)
    where list_has_any(o.ing, [{il}]) and list_has_any(r.events, [{pl}])
    group by o.primaryid
    """  # noqa: S608 - names come from our own curated table, values are quoted identifiers
    return [float(x[0]) for x in _query(q)[1]]


def _published(row: Mapping[str, str]) -> Published | None:
    kind = PublishedKind(row["published_kind"]) if row["published_kind"] else None
    if kind is None:
        return None
    if kind is PublishedKind.qualitative:
        return Published(row["published_keys"], kind)
    return Published(
        row["published_keys"],
        kind,
        float(row["published_low_days"]),
        float(row["published_high_days"]),
        float(row["published_median_days"]) if row["published_median_days"] else None,
    )


def twin_cards() -> list[dict[str, Any]]:
    pbpk = _rows("tm_pbpk")
    pop = {(str(r["drug"]).lower(), str(r["group"])): r for r in pbpk if r["kind"] == "population"}
    ss = {str(r["drug"]).lower(): r for r in pbpk if r["kind"] == "steady_state"}
    rng = random.Random(SEED)
    out: list[dict[str, Any]] = []
    for row in _curated("cascades.csv"):
        ings = row["index_ingredients"].split("|")
        pts = row["event_pts"].split("|")
        days = onset_days(ings, pts)
        card: dict[str, Any] = {
            "cascade_id": row["cascade_id"],
            "pipc_position": int(row["pipc_position"]),
            "index_class": row["index_class"],
            "event": row["event"],
            "treating_class": row["treating_class"],
            "method": row["method"],
            "method_label": {
                "pbpk": "PBPK (httk) for the index drug, plus FAERS time to onset",
                "compartmental": "minimal compartmental model with cited physiological "
                "parameters (not PBPK), plus FAERS time to onset",
                "onset_only": "FAERS time to onset only: no PBPK parameters for this drug",
            }[row["method"]],
            "note": row["note"],
            "reference_keys": row["published_keys"].split("|"),
            "onset": None,
            "risk_window": None,
            "onset_curve": None,
            "published": None,
            "agreement": None,
            "population": None,
        }
        if days:
            s: OnsetSummary = summarize(days, rng)
            card["onset"] = {
                "reports": s.n,
                "median_days": s.median_days,
                "q25_days": s.q25_days,
                "q75_days": s.q75_days,
                "median_ci_low": s.median_low,
                "median_ci_high": s.median_high,
                "small_sample": s.n < SMALL_SAMPLE,
                "zero_day_reports": sum(1 for d in days if d == 0),
                "zero_day_caveat": "a same-day interval often means the reporter gave one date "
                "for both fields rather than a genuine same-day onset; heaping at zero pulls "
                "the Weibull shape down",
                "weibull": None
                if s.fit is None
                else {
                    "shape": s.fit.shape,
                    "shape_ci_low": s.fit.shape_low,
                    "shape_ci_high": s.fit.shape_high,
                    "scale": s.fit.scale,
                    "shape_class": s.fit.shape_class.value,
                },
                "weibull_omitted_reason": None
                if s.fit is not None
                else f"fewer than {MIN_REPORTS} reports with a usable interval",
            }
            w = risk_window(s, days)
            card["risk_window"] = {
                "start_days": w.start_days,
                "end_days": w.end_days,
                "basis": w.basis,
                "coverage": "central 80 percent of the reported intervals; for a decreasing "
                "hazard (shape below 1) the upper end is far beyond the median, so the "
                "research area shows this band and the patient sentence uses the middle half",
            }
            card["middle_half_days"] = {"start_days": s.q25_days, "end_days": s.q75_days}
            if s.fit is not None:
                card["onset_curve"] = {
                    "days": ONSET_GRID,
                    "share": onset_curve(s.fit, ONSET_GRID),
                }
            pub = _published(row)
            if pub is not None:
                card["published"] = {
                    "kind": pub.kind.value,
                    "low_days": pub.low_days,
                    "high_days": pub.high_days,
                    "median_days": pub.median_days,
                    "reference_keys": row["published_keys"].split("|"),
                }
                card["agreement"] = agreement(s, pub).value
        if row["method"] == "pbpk":
            drugs: list[dict[str, Any]] = []
            for ing in ings:
                key = ing.lower()
                older, younger = pop.get((key, "older")), pop.get((key, "younger"))
                if older is None or younger is None:
                    continue
                drugs.append(
                    {
                        "drug": key,
                        "css_older_mg_per_l": {
                            "p5": older["css_p5_mg_l"],
                            "p50": older["css_p50_mg_l"],
                            "p95": older["css_p95_mg_l"],
                        },
                        "css_younger_mg_per_l": {
                            "p5": younger["css_p5_mg_l"],
                            "p50": younger["css_p50_mg_l"],
                            "p95": younger["css_p95_mg_l"],
                        },
                        "older_to_younger_ratio": float(older["css_p50_mg_l"])
                        / float(younger["css_p50_mg_l"]),
                        "days_to_90pct_steady_state": ss.get(key, {}).get("day_90pct_ss"),
                    }
                )
            if drugs:
                card["population"] = {
                    "age_range_older": "65-79",
                    "age_range_younger": "20-50",
                    "source": "HTTK-Pop virtual individuals from NHANES 2013-2018; ages above "
                    "79 are not available, so 80+ is not simulated",
                    "dose_basis": "1 mg/kg/day, steady state; relative comparison only",
                    "drugs": drugs,
                }
        out.append(card)
    return out


# --- assembly --------------------------------------------------------------------------------


def build() -> Path:
    pbpk_val, comp_val = validation_rows()
    credible = {v.drug: v.may_carry_exposure_statement for v in [*pbpk_val, *comp_val]}
    payload: dict[str, Any] = {
        "built_at": dt.datetime.now(dt.UTC).isoformat(),
        "seed": SEED,
        "simulations": SIM_N,
        "disclaimer": "In-silico hypotheses from open data. Not a treatment, not a dose, not "
        "medical advice. Research prototype, not a medical device.",
        "review_status": "AI-reviewed, pending expert review",
        "onset_subset_caveat": "Time to onset is available only for reports whose reporter gave "
        "both a complete therapy start date and a complete event date. That subset is not "
        "representative of all reports: completeness is associated with reporter type and with "
        "event seriousness. FAERS is spontaneous reporting, not incidence, and is not "
        "deduplicated across cases; counts are reports, never people.",
        "validation": {
            "rule": "credible when predicted Cmax and AUC are both within 2-fold of the "
            "published observed value; borderline within 3-fold; otherwise failed. A drug that "
            "is not credible carries no exposure-versus-potency statement.",
            "pbpk": [
                {
                    "drug": v.drug,
                    "reference_key": v.reference,
                    "observed_cmax_ng_ml": v.observed_cmax,
                    "predicted_cmax_ng_ml": v.predicted_cmax,
                    "cmax_fold_error": v.cmax_fold,
                    "observed_auc_ng_h_ml": v.observed_auc,
                    "predicted_auc_ng_h_ml": v.predicted_auc,
                    "auc_fold_error": v.auc_fold,
                    "credibility": v.credibility.value,
                    "note": v.note,
                }
                for v in pbpk_val
            ],
            "compartmental": [
                {
                    "drug": v.drug,
                    "reference_key": v.reference,
                    "observed_cmax_ng_ml": v.observed_cmax,
                    "predicted_cmax_ng_ml": v.predicted_cmax,
                    "cmax_fold_error": v.cmax_fold,
                    "observed_auc_ng_h_ml": v.observed_auc,
                    "predicted_auc_ng_h_ml": v.predicted_auc,
                    "auc_fold_error": v.auc_fold,
                    "credibility": v.credibility.value,
                    "note": v.note,
                }
                for v in comp_val
            ],
            "pbpk_summary": summary(pbpk_val),
            "compartmental_summary": summary(comp_val),
        },
        "substances": substance_cards(),
        "exposure": exposure_cards(credible),
        "cascades": twin_cards(),
        "sources": {
            name: {
                "run_id": _manifest(name)["run_id"],
                "snapshot_date": _manifest(name).get("snapshot_date"),
                "license": _manifest(name).get("license"),
                "source_urls": _manifest(name).get("source_urls", []),
                "tool_versions": _manifest(name).get("metrics", {}).get("tool_versions"),
            }
            for name in (
                "tm_molecules",
                "tm_bioactivity",
                "tm_labels",
                "tm_pbpk",
                "tm_admet",
                "faers",
                "faers_onset",
            )
        },
        "references": _curated("references.csv"),
        "faers_quality": _manifest("faers_onset").get("metrics", {}),
    }
    root = data_dir() / "timemachine"
    run = root / "runs" / dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    run.mkdir(parents=True, exist_ok=True)
    (run / "time_machine.json").write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str)
    )
    link = root / "current"
    tmp = root / "current.tmp"
    tmp.symlink_to(run.resolve(), target_is_directory=True)
    os.replace(tmp, link)
    return run


if __name__ == "__main__":
    print(build())

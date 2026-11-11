"""Re-run of the 50-drug pilot through the resolver, the unit checker and the two readers (spec
model-kit, milestone M1). Build-time code: reads the private pilot inputs (ClinicalTrials.gov
records, DailyMed label sections and tables) from a directory given on the command line, never the
network, and writes evidence rows and metrics. Research use only. Not for clinical decisions.

    python -m janus_pipelines.modelkit.pilot DATA_DIR OUT_DIR
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from janus_pipelines.jobs.modelkit_evidence import SEED_COLUMNS_FULL, evidence_row
from janus_pipelines.modelkit import reader_a, reader_b
from janus_pipelines.modelkit.derive import derive_clearance
from janus_pipelines.modelkit.model import DOSE_PARAMS, Candidate, ReaderStats
from janus_pipelines.modelkit.pairing import Paired, pair
from janus_pipelines.modelkit.resolver import IdentityTable

EXTRACTED_ON: Final = "2026-11-11"
_STAT: Final = {
    "arithmetic": "mean",
    "geometric": "geomean",
    "median": "median",
    "unspecified": "stated",
}
_POP: Final = {
    "healthy_adult": "healthy adults",
    "patients": "patients",
    "special": "special population",
}
_REASON: Final = {
    "both_readers_agree": "reader A and reader B agree on value, unit, analyte, dose and context",
    "reader_b_found_nothing": "reader B did not find this value",
    "values_differ": "reader B read a different value",
    "units_differ": "reader B read a different unit",
    "analytes_differ": "the readers disagree on the analyte",
    "doses_differ": "the readers disagree on the dose",
    "mean_types_differ": "the readers disagree on the mean type",
    "context_differs": "the readers agree on the value but differ on its context",
    "not_the_parent_drug": "both readers agree the value is not for the parent drug",
    "reader_found_no_value": "a reader found no value",
}  # fmt: skip


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower())


def candidate_row(p: Paired, table: IdentityTable) -> dict[str, str] | None:
    """One seed row (strings, as in the CSV) for a candidate of reader A and its confirmation, or
    None when the row cannot be stored (an observation without a dose from the arm definition)."""
    a = p.a
    ctx = a.context
    if a.parameter in DOSE_PARAMS and a.dose_mg is None:
        return None
    parent = a.analyte == "parent"
    bound = "bound" in a.notes
    rng = a.stat.spread_type == "range" and a.stat.spread_low and a.stat.spread_high
    statistic = "lower_bound" if bound else "range_geomean" if rng else _STAT[a.stat.center_type]
    if bound and rng:
        return None
    inter = bool(ctx.coadministered)
    confirm_reason = _REASON.get(p.result.reason, p.result.reason)
    if p.result.differing:
        confirm_reason += " (" + ", ".join(p.result.differing) + ")"
    name = table.by_key[a.drug_key]
    spread = a.stat.spread_type
    row = {
        "drug_key": a.drug_key,
        "analyte": sorted(name.names)[0] if parent else f"not the parent drug ({a.analyte})",
        "analyte_class": a.analyte,
        "parameter": a.parameter,
        "value": repr(a.value),
        "value_low": repr(a.stat.spread_low) if rng else "",
        "value_high": repr(a.stat.spread_high) if rng else "",
        "statistic": statistic,
        "unit": a.unit,
        "dose": "" if a.dose_mg is None else repr(a.dose_mg),
        "dose_unit": "" if a.dose_mg is None else "mg",
        "route": ctx.route if ctx.route in ("oral", "iv") else "unknown",
        "regimen": ctx.regimen if ctx.regimen in ("single", "multiple") else "unknown",
        "interval_h": "" if a.interval_h is None else repr(a.interval_h),
        "population": _POP.get(ctx.population, ""),
        "n_subjects": "" if a.n_subjects is None else str(a.n_subjects),
        "formulation": ctx.formulation,
        "coadministered": "true" if inter else "false",
        "study_id": a.study_id,
        "source_id": a.source_id,
        "source_locator": a.locator,
        "source_version": a.source_version,
        "quote": a.quote or "(see locator)",
        "reader_a": "agree",
        "reader_b": "agree" if p.result.confirmed else "disagree",
        "confirm_reason": confirm_reason,
        "note": "; ".join(n for n in a.notes if n),
        "extracted_at": EXTRACTED_ON,
        "arm_id": a.arm_id,
        "origin": "reader_pair",
        "derivation": "",
        "evidence_kind": "interaction" if inter else "pk",
        "food": ctx.food,
        "dispersion_type": spread if spread in ("sd", "cv_percent", "range", "ci95", "iqr", "se") else "none",
        "dispersion_low": _pos(a.stat.spread_low),
        "dispersion_high": _pos(a.stat.spread_high),
    }  # fmt: skip
    return row


def _pos(x: float | None) -> str:
    return repr(x) if x is not None and x > 0 else ""


def _clean_quote(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:360]


def run(data: Path, out: Path) -> dict[str, Any]:
    """Read every source, pair the readers, build rows. Returns the metrics."""
    repo = Path(__file__).resolve().parents[3]
    table = IdentityTable.from_csv(
        (repo / "data" / "modelkit" / "identity_m1.csv").read_text("utf-8")
    )
    pilot = json.loads((data / "pkdata" / "out" / "pilot.json").read_text("utf-8"))["drugs"]
    docs = json.loads((data / "pk1sim" / "out" / "spl_docs.json").read_text("utf-8"))
    tables_all = json.loads((data / "pk1sim" / "out" / "tables.json").read_text("utf-8"))
    by_set: dict[str, dict[str, Any]] = {}
    for k, v in tables_all.items():
        by_set.setdefault(k.split("#")[0], {})[k] = v
    out.mkdir(parents=True, exist_ok=True)
    stats = {s: {r: ReaderStats() for r in "ab"} for s in ("clinicaltrials_gov", "dailymed_spl")}
    pairs: list[Paired] = []
    only_b: list[Candidate] = []
    per_drug: dict[str, dict[str, int]] = {}
    for d in pilot:
        key = slug(d["name"])
        a_rows: list[Candidate] = []
        b_rows: list[Candidate] = []
        sid = d["set_id"]
        a_rows += reader_a.read_label(
            docs[sid], by_set.get(sid, {}), sid, key, table, stats["dailymed_spl"]["a"]
        )
        b_rows += reader_b.read_label(
            docs[sid], by_set.get(sid, {}), sid, key, table, stats["dailymed_spl"]["b"]
        )
        studies = json.loads(
            (data / "pkdata2" / "dl_ctgov" / f"{d['key']}.json").read_text("utf-8")
        )
        for s in studies:
            a_rows += reader_a.read_ctgov(s, key, table, stats["clinicaltrials_gov"]["a"])
            b_rows += reader_b.read_ctgov(s, key, table, stats["clinicaltrials_gov"]["b"])
        p, left = pair(a_rows, b_rows)
        pairs += p
        only_b += left
        per_drug[key] = {
            "a": len(a_rows),
            "b": len(b_rows),
            "confirmed": sum(x.result.confirmed for x in p),
        }
    rows: list[dict[str, str]] = []
    dropped = Counter[str]()
    seen: set[tuple[str, str, str, str]] = set()
    for p in pairs:
        r = candidate_row(p, table)
        if r is None:
            dropped["observation_without_dose"] += 1
            continue
        r["quote"] = _clean_quote(r["quote"])
        k = (r["drug_key"], r["parameter"], r["source_locator"], r["value"])
        if k in seen:
            dropped["duplicate"] += 1
            continue
        seen.add(k)
        try:
            evidence_row(r, "check")
        except ValueError as exc:
            dropped["invalid:" + str(exc).split(":", 1)[-1].strip()[:50]] += 1
            continue
        rows.append(r)
    dicts = [evidence_row(r, "x") for r in rows]
    derived = derive_clearance(dicts)
    for dd in derived:
        row = {c: ("" if dd.get(c) is None else _fmt(dd[c])) for c in SEED_COLUMNS_FULL}
        row["coadministered"] = "true" if dd["coadministered"] else "false"
        row["dose_unit"] = "mg"
        row["reader_a"], row["reader_b"] = dd["reader_a"], dd["reader_b"]
        row["quote"] = _clean_quote(str(dd["quote"]))
        try:
            evidence_row(row, "derived")
        except ValueError as exc:
            dropped["derived_invalid:" + str(exc)[:40]] += 1
            continue
        rows.append(row)
    write_csv(out / "rows_reader_output.csv", rows)  # exactly what the readers confirmed
    enriched = enrich_label_rows(rows, docs, {slug(d["name"]): d["set_id"] for d in pilot})
    write_csv(out / "rows_all.csv", rows)
    metrics = summarise(pairs, only_b, rows, stats, dropped, per_drug)
    metrics["label_rows_with_formulation_or_route_from_dosage_forms"] = enriched
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1, sort_keys=True), "utf-8")
    return metrics


_NOT_PLAIN_ORAL: Final = re.compile(
    r"EXTENDED|DELAYED|CONTROLLED|SUSTAINED|PATCH|TRANSDERMAL|INJECT|IMPLANT|INTRAVENOUS|GEL|CREAM|"
    r"OINTMENT|INHAL|SPRAY|SUPPOSITORY|OPHTHALMIC|LYOPHILIZED|EMULSION|DEPOT|VAGINAL|AEROSOL|"
    r"POWDER, FOR SOLUTION|SOLUTION, CONCENTRATE|FILM$|SYSTEM"
)


def enrich_label_rows(
    rows: list[dict[str, str]], docs: Mapping[str, Any], sets: Mapping[str, str]
) -> int:
    """Where a label sentence says nothing about the formulation or the route, take them from the
    label's own dosage forms and routes (structured data of the same label): only when every form is
    a plain oral form (no extended, delayed, depot, injectable, topical or other special form) and
    the only route is ORAL. This step is separate from reader confirmation and is noted on the row."""
    n = 0
    for r in rows:
        if r["source_id"] != "dailymed_spl" or r["origin"] != "reader_pair":
            continue
        doc = docs[sets[r["drug_key"]]]
        forms = [str(x).upper() for x in doc.get("forms", [])]
        routes = [str(x).upper() for x in doc.get("routes", [])]
        plain = (
            bool(forms) and not any(_NOT_PLAIN_ORAL.search(f) for f in forms) and routes == ["ORAL"]
        )
        if not plain:
            continue
        changed = False
        if r["formulation"] == "unspecified":
            r["formulation"], changed = "immediate_release", True
        if r["route"] == "unknown":
            r["route"], changed = "oral", True
        if changed:
            r["note"] = "; ".join(
                x for x in (r["note"], "formulation and route from the label's dosage forms") if x
            )
            n += 1
    return n


def _fmt(v: Any) -> str:
    return repr(v) if isinstance(v, float) else str(v)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(SEED_COLUMNS_FULL), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - h) / d), min(1.0, (c + h) / d)


def summarise(
    pairs: list[Paired],
    only_b: list[Candidate],
    rows: Sequence[Mapping[str, str]],
    stats: dict[str, dict[str, ReaderStats]],
    dropped: Counter[str],
    per_drug: dict[str, dict[str, int]],
) -> dict[str, Any]:
    out: dict[str, Any] = {"by_source": {}}
    for src in ("clinicaltrials_gov", "dailymed_spl"):
        ps = [p for p in pairs if p.a.source_id == src]
        parents = [p for p in ps if p.a.analyte == "parent"]
        conf = [p for p in parents if p.result.confirmed]
        w = wilson(len(conf), len(parents))
        out["by_source"][src] = {
            "reader_a_candidates": len(ps),
            "reader_a_parent_candidates": len(parents),
            "confirmed": len(conf),
            "agreement_share_parent": round(len(conf) / len(parents), 4) if parents else None,
            "agreement_wilson": w,
            "analyte_classes": dict(Counter(p.a.analyte for p in ps)),
            "reasons_parent": dict(Counter(p.result.reason for p in parents)),
            "reader_b_only": sum(1 for c in only_b if c.source_id == src),
            "a_skipped": stats[src]["a"].skipped,
            "b_skipped": stats[src]["b"].skipped,
        }
    out["rows"] = len(rows)
    out["rows_confirmed"] = sum(
        1
        for r in rows
        if r["reader_a"] == r["reader_b"] == "agree" and r["analyte_class"] == "parent"
    )
    out["rows_derived"] = sum(1 for r in rows if r["origin"] == "derived")
    out["dropped_rows"] = dict(dropped)
    out["per_drug"] = per_drug
    return out


if __name__ == "__main__":
    m = run(Path(sys.argv[1]), Path(sys.argv[2]))
    print(
        json.dumps({k: v for k, v in m.items() if k not in ("per_drug",)}, indent=1, sort_keys=True)
    )

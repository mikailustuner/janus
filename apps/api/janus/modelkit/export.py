"""Exports of a parameter set (requirement 4): Janus engine JSON and R/mrgsolve, each with
provenance, references and licences, as a deterministic zip. Pure. Research use only. Not for
clinical decisions.

The Janus engine file is a point model: the `Params` of `janus.simulation.compartmental` with all
spreads 1.0 and bioavailability fixed, because no variability is evidenced. The same engine code
gives the reference curve of the mrgsolve round-trip test.
"""

from __future__ import annotations

import io
import json
import zipfile
from functools import cache
from typing import Any

from janus.modelkit.builder import ParameterSet
from janus.modelkit.evidence import Ev
from janus.modelkit.reasons import text
from janus.modelkit.validate import Validation
from janus.paths import repo_root
from janus.simulation.compartmental import Params

RESEARCH_USE = "Research use only. Not for clinical decisions."
NO_REVIEW = "Expert review has not yet been done."
EXPERIMENTAL = "Experimental: this model kit is an early research preview."
STATEMENTS = (RESEARCH_USE, NO_REVIEW, EXPERIMENTAL)
MRGSOLVE_LICENCE = "GPL (>= 2)"
MRGSOLVE_PINNED = "2.0.1"
TARGETS = ("janus", "mrgsolve")
FIXED_TIME = (2026, 11, 11, 0, 0, 0)


class NotExportableError(ValueError):
    """The set cannot be exported (incomplete: no absorption rate)."""


@cache
def source_meta() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name in ("sources_m0.json", "sources_m1.json"):
        path = repo_root() / "data" / "modelkit" / name
        out.update(json.loads(path.read_text(encoding="utf-8")))
    return out


def engine_params(ps: ParameterSet) -> Params:
    """The Janus engine parameters of a complete set (a point model)."""
    if not ps.complete:
        raise NotExportableError("incomplete_set")
    f, cl, v, ka = ps.engine()
    assert ka is not None  # noqa: S101 - complete means ka exists
    return Params(f=f, ka=ka, cl=cl, v=v, tlag=0.0, ka_gsd=1.0, cl_gsd=1.0, v_gsd=1.0, f_fixed=True)


def example_dose_mg(val: Validation | None) -> float:
    """A dose that appears in the validation observations (a study dose), else 1 mg. Never advice."""
    if val and val.points:
        return float(sorted(p.dose_mg for p in val.points)[0])
    return 1.0


def engine_json(ps: ParameterSet, val: Validation | None) -> dict[str, Any]:
    p = engine_params(ps)
    return {
        "schema": "janus.modelkit.engine/1",
        "statements": list(STATEMENTS),
        "drug": ps.drug_key,
        "model": "one-compartment, first-order absorption (janus.timemachine.pk.OneCompartment)",
        "label": "point model from cited evidence; no between-subject variability is evidenced",
        "apparent": ps.apparent,
        "basis": ps.basis,
        "params": p.__dict__,
        "params_note": "spread values 1.0 and f_fixed true: a single curve, not a population",
        "units": {
            "dose": "mg",
            "time": "h",
            "cl": "L/h",
            "v": "L",
            "ka": "1/h",
            "f": "fraction",
            "concentration": "ng/mL",
        },
        "apparent_note": (
            "CL and V are CL/F and V/F (apparent); f is 1 because bioavailability is inside them"
            if ps.apparent
            else None
        ),
        "example_dose_mg": example_dose_mg(val),
        "example_dose_note": "a dose that appears in the evidence; not a dose recommendation",
        "validation_status": val.status if val else None,
        "warnings": [{"code": w, "text": text(w)} for w in ps.warnings],
    }


def mrgsolve_cpp(ps: ParameterSet) -> str:
    p = engine_params(ps)
    return f"""$PROB {ps.drug_key}: Janus model kit starter model (experimental)
// {RESEARCH_USE} {NO_REVIEW}
// One compartment, first-order absorption. Units: dose mg, time h, CL L/h, V L, KA 1/h,
// concentration CP in ng/mL. {"CL and V are apparent (CL/F, V/F); F is 1." if ps.apparent else ""}
// Values and their sources: provenance.json. This is a point model: no variability is evidenced.

$PARAM
CL = {p.cl!r}
V = {p.v!r}
KA = {p.ka!r}
F = {p.f!r}
TLAG = {p.tlag!r}

$CMT GUT CENT

$MAIN
F_GUT = F;
ALAG_GUT = TLAG;

$ODE
dxdt_GUT = -KA * GUT;
dxdt_CENT = KA * GUT - (CL / V) * CENT;

$SET rtol = 1e-10, atol = 1e-14

$TABLE
double CP = 1000.0 * CENT / V;

$CAPTURE CP
"""


def example_r(ps: ParameterSet, val: Validation | None) -> str:
    dose = example_dose_mg(val)
    return f"""# {ps.drug_key}: example use of model.cpp with mrgsolve ({MRGSOLVE_PINNED} tested)
# {RESEARCH_USE} {NO_REVIEW}
# The dose below is a dose that appears in the evidence; it is an input to a modelling
# exercise, not a dose recommendation and not for any person.
library(mrgsolve)

mod <- mread("model", ".")        # reads model.cpp from the current folder
dose_mg <- {dose!r}
out <- mrgsim_e(mod, ev(amt = dose_mg, cmt = "GUT"), end = 72, delta = 0.25)
d <- as.data.frame(out)
cat(sprintf("Cmax %.4g ng/mL at %.2f h\\n", max(d$CP), d$time[which.max(d$CP)]))
plot(d$time, d$CP, type = "l", xlab = "time (h)", ylab = "concentration (ng/mL)",
     main = "{ps.drug_key} (experimental model kit, research use only)")
"""


def provenance(
    ps: ParameterSet, val: Validation | None, rows: list[Ev], release: dict[str, Any]
) -> dict[str, Any]:
    by_id = {r.eid: r for r in rows}
    used = sorted(ps.used)
    meta = source_meta()
    pts = [p.eid for p in val.points] if val else []
    studies = sorted({by_id[e].study for e in [*used, *pts]})
    return {
        "kit": {
            "name": "Janus drug model starter kit",
            "status": "experimental",
            "release": release["run_id"],
            "evidence_snapshot": release["snapshot_date"],
            "pipeline_version": "modelkit-evidence-1.0",
        },
        "statements": list(STATEMENTS),
        "drug": ps.drug_key,
        "model": {
            "family": ps.model,
            "reason": ps.model_reason,
            "basis": ps.basis,
            "apparent": ps.apparent,
        },
        "parameters": [
            {
                "name": q.name,
                "label": q.label,
                "value": q.value,
                "unit": q.unit,
                "confidence_class": q.cls,
                "n_studies": q.n_studies,
                "between_study_cv": q.spread_cv,
                "derivation": q.derivation,
                "note": q.note,
                "evidence": list(q.evidence),
            }
            for q in ps.params
        ],
        "evidence": [
            {
                "id": e,
                "parameter": by_id[e].parameter,
                "value_as_stated": by_id[e].value,
                "unit_as_stated": by_id[e].unit,
                "value_canonical": by_id[e].value_si,
                "study": by_id[e].study_id,
                "source": by_id[e].source_id,
                "locator": by_id[e].source_locator,
                "source_version": by_id[e].source_version,
                "quote": by_id[e].quote,
                "reader_a": by_id[e].reader_a,
                "reader_b": by_id[e].reader_b,
                "population": by_id[e].population,
                "route": by_id[e].route,
            }
            for e in used
        ],
        "left_out": [{"id": e, "reason": why, "reason_text": text(why)} for e, why in ps.left_out],
        "held_out_studies": [{"source": s, "study": t} for s, t in ps.test_studies],
        "warnings": [{"code": w, "text": text(w)} for w in ps.warnings],
        "validation": None if val is None else validation_summary(val, by_id),
        "sources": {f"{s}:{t}": meta.get(f"{s}:{t}") for s, t in studies},
    }


def validation_summary(val: Validation, by_id: dict[str, Ev]) -> dict[str, Any]:
    return {
        "observations": [
            {
                "id": p.eid,
                "metric": p.metric,
                "study": p.study_id,
                "dose_mg": p.dose_mg,
                "observed": p.observed,
                "predicted": p.predicted,
                "ratio": p.ratio,
                "within_2_fold": p.within_2_fold,
                "locator": by_id[p.eid].source_locator,
                "quote": by_id[p.eid].quote,
            }
            for p in val.points
        ],
        "status": val.status,
        "reasons": [{"code": c, "text": text(c)} for c in val.reasons],
        "excluded_observations": [
            {"id": i, "reason": c, "reason_text": text(c)} for i, c in val.excluded
        ],
        "metrics": [m.__dict__ for m in val.metrics],
        "suspect": [{"code": c, "text": text(c)} for c in val.suspect],
        "failed_points": list(val.failed_points),
        "interval": text(val.interval),
        "note": "n is small; ratios are predicted / observed; shown with their counts",
    }


def _bib_key(key: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in key)


def references_bib(prov: dict[str, Any]) -> str:
    out = [f"% {RESEARCH_USE} {NO_REVIEW}", "% Sources of the values in provenance.json."]
    for key, m in sorted(prov["sources"].items()):
        if not m:
            continue
        title = str(m["title"]).replace("{", "(").replace("}", ")")
        if m["type"] == "article":
            out.append(
                f"@article{{{_bib_key(key)},\n  author = {{{' and '.join(m['authors'])}}},\n"
                f"  title = {{{title}}},\n  journal = {{{m['journal']}}},\n  year = {{{m['year']}}},\n"
                f"  doi = {{{m['doi']}}},\n  url = {{{m['url']}}},\n"
                f"  note = {{Licence: {m['licence']}. Values transcribed from a table, units converted.}}\n}}"
            )
        else:
            out.append(
                f"@misc{{{_bib_key(key)},\n  title = {{{title}}},\n  howpublished = {{\\url{{{m['url']}}}}},\n"
                f"  note = {{Accessed {m['retrieved']}. Licence: {m['licence']}.}}\n}}"
            )
    return "\n\n".join(out) + "\n"


def licenses_txt(prov: dict[str, Any]) -> str:
    srcs = {k.split(":")[0] for k in prov["sources"]}
    lines = [
        RESEARCH_USE,
        NO_REVIEW,
        "",
        "Janus drug model kit: licences and attributions of the sources behind this export.",
        "The model files themselves are generated by Janus (Apache-2.0). Quoted source text keeps the terms below.",
        "",
    ]
    if "clinicaltrials_gov" in srcs:
        lines += [
            "ClinicalTrials.gov (U.S. National Library of Medicine)",
            "  Source of the data: ClinicalTrials.gov. The date each record was last updated and when Janus",
            "  retrieved it is in provenance.json (sources). Modifications by Janus: values were re-typed from the",
            "  posted results, units converted to canonical units, rows filtered by analyte, arm and population,",
            "  and short parts of the posted text quoted. Records are entered by sponsors; NLM checks format, not",
            "  scientific validity. Some records may carry third-party copyright. Terms:",
            "  https://clinicaltrials.gov/about-site/terms-conditions",
            "",
        ]
    if "dailymed_spl" in srcs:
        lines += [
            "DailyMed labels (U.S. National Library of Medicine / U.S. Food and Drug Administration)",
            "  Public domain (U.S. government work). Label text is written by the manufacturer. A quoted sentence",
            "  is label text, not an assessment by Janus, FDA or NLM. Not an FDA or NLM endorsement.",
            "",
        ]
    if "drugsatfda_review" in srcs:
        lines += [
            "Drugs@FDA clinical pharmacology reviews (U.S. Food and Drug Administration)",
            "  Public domain unless noted (sponsor material reproduced in a review may be an exception).",
            "  Scanned pages were read by optical character recognition; numbers were checked against the page image.",
            "",
        ]
    for _key, m in sorted(prov["sources"].items()):
        if m and m["type"] == "article":
            lines += [
                f"{m['title']} ({', '.join(m['authors'])}; {m['journal']} {m['year']}; doi:{m['doi']}; {m['pmcid']})",
                f"  Licence: {m['licence']}. Credit the authors and the source article, link the licence, and note",
                "  that changes were made: values transcribed from a table, units converted, short parts quoted.",
                "  No endorsement by the authors is implied.",
                "",
            ]
    lines += [
        "R/mrgsolve: model.cpp is meant to be run with the mrgsolve R package (GPL (>= 2)); it is not included.",
        f"Tested with mrgsolve {MRGSOLVE_PINNED}.",
        "",
    ]
    return "\n".join(lines)


def readme_txt(ps: ParameterSet, target: str) -> str:
    what = (
        "janus-model.json (Janus engine parameters)"
        if target == "janus"
        else "model.cpp and example.R (R/mrgsolve)"
    )
    return "\n".join(
        [
            f"Janus model kit (experimental): {ps.drug_key}",
            RESEARCH_USE,
            NO_REVIEW,
            EXPERIMENTAL,
            "",
            f"Files: {what}, provenance.json (every value to its source and quote), references.bib, LICENSES.txt.",
            "This is a starting model from published evidence, with a validation status in provenance.json.",
            "It is not a dose calculator, not for any person, and it does not say a medicine or dose is safe.",
            "",
        ]
    )


def build_zip(files: dict[str, str]) -> bytes:
    """Deterministic zip: sorted names, fixed timestamps, no extra fields."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[name].encode("utf-8"))
    return buf.getvalue()


def export_files(
    target: str, ps: ParameterSet, val: Validation | None, rows: list[Ev], release: dict[str, Any]
) -> dict[str, str]:
    if target not in TARGETS:
        raise ValueError("unknown target")
    prov = provenance(ps, val, rows, release)
    common = {
        "provenance.json": json.dumps(prov, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        "references.bib": references_bib(prov),
        "LICENSES.txt": licenses_txt(prov),
        "README.txt": readme_txt(ps, target),
    }
    if target == "janus":
        common["janus-model.json"] = (
            json.dumps(engine_json(ps, val), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        )
    else:
        common["model.cpp"] = mrgsolve_cpp(ps)
        common["example.R"] = example_r(ps, val)
    return common

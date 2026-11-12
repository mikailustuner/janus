"""The versioned model kit data package (plan section 10; milestone M6), built but not uploaded.

`python -m janus.modelkit.package --out DIR` writes, from the current `modelkit_evidence` release
(or `--run RUN_DIR`): the published evidence rows, the US-label special-population statements, the
parameter sets, the validation report, a licence and attribution manifest (with the
ClinicalTrials.gov processing date and the statement of changes), a README, a Frictionless
`datapackage.json` with a hash per file, and a `.zenodo.json` metadata draft WITHOUT a DOI (the
owner decides on the DOI and the creators). Deterministic: the same release gives the same bytes.

Only publishable rows enter it: a row of a source the release publishes (ClinicalTrials.gov, the
DailyMed label sections, the M0 seed's document rows, or a document source whose measured precision
published it), a PMC row only with a CC BY or CC0 licence. Anything else stops the build: the store
should never hold such a row. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, Final, cast

from janus.modelkit import export as ex
from janus.modelkit.builder import ParameterSet
from janus.modelkit.evidence import PIPELINE, Ev
from janus.modelkit.store import Release, build_release
from janus.paths import repo_root

NAME: Final = "janus-modelkit-package"
VERSION: Final = "1.0.0"
ALWAYS_PUBLISHED: Final = frozenset({"clinicaltrials_gov", "dailymed_spl"})
DOCUMENT_SOURCES: Final = frozenset({"pmc_oa", "drugsatfda_review"})
# PMC rows: CC BY or CC0 only (never NC, ND or SA), as the M5 licence checks
OPEN_LICENCE: Final = re.compile(r"\bcc0\b|\bcc[ -]by\b(?![ -]?(?:nc|nd|sa)\b)", re.IGNORECASE)
CTGOV_PROCESSED: Final = "2026-11-11"  # bulk file read by modelkit_ctgov (NOTICE, sources.toml)
STATEMENTS: Final = (
    ex.RESEARCH_USE,
    ex.NO_REVIEW,
    ex.EXPERIMENTAL,
    "Every value was read and confirmed by automated readers; no person has checked it.",
)
# the evidence row as the store keeps it (Ev's fields; `eid` is the stable evidence id)
FIELDS: Final = tuple(f for f in Ev.__dataclass_fields__ if f != "eid")
EVIDENCE_COLUMNS: Final = ("evidence_id", *FIELDS)
SP_FILE: Final = ("data", "modelkit", "special_populations.csv")


def publishable(r: Ev, published_documents: frozenset[str]) -> str | None:
    """Why a row may not be published, or None."""
    if r.source_id in ALWAYS_PUBLISHED:
        return None
    if r.source_id not in DOCUMENT_SOURCES:
        return f"unknown source {r.source_id}"
    if r.origin != "m0_annotation" and r.source_id not in published_documents:
        return f"held-back source {r.source_id}"
    if r.source_id == "pmc_oa" and not OPEN_LICENCE.search(r.source_version):
        return "PMC row without a CC BY or CC0 licence"
    return None


def published_documents(metrics: Mapping[str, Any]) -> frozenset[str]:
    """The document sources whose measured precision published them (precision_documents.json)."""
    raw = metrics.get("precision_documents")
    prec = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
    return frozenset(
        s
        for s, v in prec.items()
        if isinstance(v, dict) and cast(dict[str, Any], v).get("published") is True
    )


def _csv(header: Sequence[str], rows: Sequence[Sequence[Any]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return buf.getvalue().encode("utf-8")


def _json(obj: Any) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def evidence_file(rows: Sequence[Ev]) -> bytes:
    return _csv(
        EVIDENCE_COLUMNS,
        [[r.eid, *(getattr(r, c) for c in FIELDS)] for r in rows],
    )


def sets_files(rel: Release) -> tuple[bytes, bytes]:
    flat: list[list[Any]] = []
    full: list[dict[str, Any]] = []
    for key, d in rel.drugs.items():
        ps = d.built
        if not isinstance(ps, ParameterSet):
            continue
        full.append(
            {
                "drug": key, "model": ps.model, "basis": ps.basis, "apparent": ps.apparent,
                "complete": ps.complete, "missing": list(ps.missing), "warnings": list(ps.warnings),
                "implied_half_life_h": ps.implied_half_life_h,
                "stated_half_life_h": ps.stated_half_life_h,
                "parameters": [asdict(p) for p in ps.params], "used_evidence": list(ps.used),
                "test_studies": [list(t) for t in ps.test_studies],
            }
        )  # fmt: skip
        for p in ps.params:
            flat.append(
                [key, p.name, p.label, p.value, p.unit, p.cls, p.n_studies, p.spread_cv,
                 p.derivation, p.note, "|".join(p.evidence)]
            )  # fmt: skip
    header = ("drug", "parameter", "label", "value", "unit", "confidence_class", "n_studies",
              "between_study_cv", "derivation", "note", "evidence_ids")  # fmt: skip
    return _csv(header, flat), _json(full)


def validation_file(rel: Release) -> bytes:
    s = rel.system
    return _json(
        {
            "rule": "Validated only if AUC and Cmax are both tested and every held-out point is "
            "within [0.5, 2] (predicted / observed); Failed if any point is outside; otherwise Not "
            "validated. The system result is interpretable only with at least 10 drugs with both "
            "metrics tested.",
            "system": asdict(s),
            "drugs": {
                k: {
                    "status": d.validation.status,
                    "reasons": list(d.validation.reasons),
                    "metrics": [asdict(m) for m in d.validation.metrics],
                    "points": [asdict(p) for p in d.validation.points],
                    "failed_points": list(d.validation.failed_points),
                    "suspect": list(d.validation.suspect),
                }
                for k, d in rel.drugs.items()
            },
        }
    )


CTGOV_TERMS: Final = {
    "licence": (
        "Free to reuse with attribution (ClinicalTrials.gov terms and conditions); some records "
        "may carry third-party copyright"
    ),
    "attribution": "Source of the data: ClinicalTrials.gov.",
    "processed": (
        f"The official bulk file of all study records, processed {CTGOV_PROCESSED}; each row "
        "gives the date its record was last updated (source_version)."
    ),
    "changes": (
        "Values were re-typed from the posted results, units were converted to canonical units "
        "(for example mL/min to L/h), rows were filtered by analyte, arm and population, and "
        "short parts of the posted text are quoted. The registry text is not changed beyond that."
    ),
    "note": (
        "Records are entered by sponsors; NLM checks format, not scientific validity. Not an NLM "
        "endorsement."
    ),
    "terms": "https://clinicaltrials.gov/about-site/terms-conditions",
}
LABEL_TERMS: Final = {
    "licence": "Public domain (U.S. government work); label text is written by the manufacturer",
    "attribution": (
        "DailyMed, U.S. National Library of Medicine; label set id, version and effective date "
        "with every row. Not an FDA or NLM endorsement."
    ),
}
SP_TERMS: Final = {
    "licence": "openFDA drug label files (CC0 1.0); label text is written by the manufacturer",
    "attribution": (
        "openFDA drug label bulk files; quoted with label set id, version and effective date. Not "
        "an FDA endorsement."
    ),
}
FDA_TERMS: Final = {
    "licence": "Public domain unless noted (U.S. government work)",
    "attribution": (
        "Drugs@FDA review documents, U.S. Food and Drug Administration. Not an FDA endorsement."
    ),
}


def licences(rows: Sequence[Ev], meta: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    n = Counter(r.source_id for r in rows)
    articles = sorted({r.study_id for r in rows if r.source_id == "pmc_oa"})
    return {
        "package_licence": (
            "Each row keeps the terms of its own source (below). The parameter sets and the "
            "validation report are derived by Janus from those rows and carry the same attribution "
            "duties; Janus's own code is Apache-2.0."
        ),
        "sources": {
            "clinicaltrials_gov": {"rows": n.get("clinicaltrials_gov", 0), **CTGOV_TERMS},
            "dailymed_spl": {"rows": n.get("dailymed_spl", 0), **LABEL_TERMS},
            "special_populations": SP_TERMS,
            "pmc_oa": {
                "rows": n.get("pmc_oa", 0),
                "licence": "CC BY or CC0, per article (stated in source_version)",
                "articles": [{"pmcid": a, **dict(meta.get(f"pmc_oa:{a}", {}))} for a in articles],
            },
            "drugsatfda_review": {"rows": n.get("drugsatfda_review", 0), **FDA_TERMS},
        },
    }


def readme(rel: Release, c: Mapping[str, int], version: str) -> bytes:
    lines = [
        f"# Janus drug model starter kit: data package {version}",
        "",
        *STATEMENTS,
        "",
        f"Evidence release `{rel.run_id}` (snapshot {rel.snapshot_date}). Built by",
        "`python -m janus.modelkit.package` from that release; the same release gives the same",
        "files.",
        "",
        "## Files",
        f"- `evidence.csv`: every published evidence row ({c['evidence']} rows, {c['confirmed']}",
        "  confirmed by both automated readers). A row with `confirmed = False` is evidence only",
        "  and never builds or tests a set. `value` and `unit` are as the source states them;",
        "  `value_si` is canonical (L, L/h, h, fraction, ng/mL, ng*h/mL; per-kg values keep their",
        "  per-kg unit); `dose` is in mg.",
        f"- `special_populations.csv`: {c['special_populations']} exposure ratios of older adults",
        "  and of renal and hepatic impairment as US labels state them, quoted.",
        f"- `parameter_sets.csv`, `parameter_sets.json`: {c['sets']} one-compartment parameter",
        "  sets with their evidence ids, confidence classes and derivations.",
        "- `validation.json`: the status of every drug, its held-out points, the system report.",
        "- `licences.json`: the terms, attribution and statement of changes of each source.",
        "- `datapackage.json`: Frictionless descriptor with a sha256 hash and rows per file.",
        "",
        "## How to read it",
        f"- Status: Validated {c['validated']}, Failed {c['failed']}, Not validated",
        f"  {c['not_validated']}. A status describes how a set did against a handful of held-out",
        "  studies; it is not a statement about the medicine.",
        "- This is not a dose calculator and it gives no advice about any person.",
        f"- Cite: Janus drug model starter kit data package, version {version}.",
        "  A DOI has not been assigned yet.",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


TITLE: Final = "Janus drug model starter kit: evidence, parameter sets and validation"
DESCRIPTION: Final = (
    "Pharmacokinetic evidence rows quoted from ClinicalTrials.gov posted results and US labels, "
    "read and confirmed by two independent automated readers, one-compartment parameter sets "
    "built from them, and a strict held-out validation report."
)
KEYWORDS: Final = (
    "pharmacokinetics", "ClinicalTrials.gov", "drug labels", "evidence", "parameter sets",
    "model validation",
)  # fmt: skip
ROW_TERMS: Final = "Each row keeps the terms of its own source (licences.json)"


def zenodo(version: str, rel: Release) -> bytes:
    """A Zenodo metadata draft: no DOI and no creator (the owner adds both before any upload)."""
    return _json(
        {
            "title": f"{TITLE} ({version})",
            "upload_type": "dataset",
            "version": version,
            "description": f"{DESCRIPTION} {' '.join(STATEMENTS)}",
            "access_right": "open",
            "license": "other-at",
            "keywords": list(KEYWORDS),
            "related_identifiers": [
                {
                    "identifier": "https://github.com/mikailustuner/janus",
                    "relation": "isSupplementTo",
                }
            ],
            "notes": (
                f"Evidence release {rel.run_id}. {ROW_TERMS}. Creators, licence choice and DOI are "
                "decided by the project owner before any upload."
            ),
            "creators": [],
        }
    )


def build(rel: Release, root: Path) -> dict[str, bytes]:
    """The files of the package, by name. Raises ValueError on a row that may not be published."""
    rows = sorted((r for d in rel.drugs.values() for r in d.rows), key=lambda r: r.eid)
    docs = published_documents(rel.manifest_metrics)
    bad = [(r.eid, why) for r in rows if (why := publishable(r, docs))]
    if bad:
        raise ValueError(f"{len(bad)} rows may not be published, first: {bad[0]}")
    sp = (root.joinpath(*SP_FILE)).read_bytes()
    sets_csv, sets_json = sets_files(rel)
    st = rel.system.by_status
    counts = {
        "evidence": len(rows), "confirmed": sum(r.confirmed for r in rows),
        "special_populations": max(0, sp.decode("utf-8").count("\n") - 1),
        "sets": sum(isinstance(d.built, ParameterSet) for d in rel.drugs.values()),
        "validated": st.get("validated", 0), "failed": st.get("failed", 0),
        "not_validated": st.get("not_validated", 0),
    }  # fmt: skip
    version = f"{VERSION}+{rel.run_id}"
    files = {
        "evidence.csv": evidence_file(rows),
        "special_populations.csv": sp,
        "parameter_sets.csv": sets_csv,
        "parameter_sets.json": sets_json,
        "validation.json": validation_file(rel),
        "licences.json": _json(licences(rows, ex.source_meta())),
        "README.md": readme(rel, counts, version),
        ".zenodo.json": zenodo(version, rel),
    }
    resources: list[dict[str, Any]] = []
    for name, data in sorted(files.items()):
        res: dict[str, Any] = {
            "name": name.lstrip(".").replace(".", "-").lower(),
            "path": name,
            "bytes": len(data),
            "hash": "sha256:" + hashlib.sha256(data).hexdigest(),
        }
        if name.endswith(".csv"):
            res["rows"] = max(0, len(list(csv.reader(io.StringIO(data.decode("utf-8"))))) - 1)
        resources.append(res)
    files["datapackage.json"] = _json(
        {
            "name": NAME, "version": version, "created": rel.snapshot_date,
            "title": TITLE,
            "description": " ".join(STATEMENTS),
            "homepage": "https://github.com/mikailustuner/janus",
            "licenses": [{"name": "other-at", "title": ROW_TERMS}],
            "resources": resources,
        }
    )  # fmt: skip
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the model kit data package (not uploaded).")
    ap.add_argument("--out", type=Path, required=True, help="output directory (replaced)")
    ap.add_argument("--run", type=Path, help="evidence run directory (default: the current one)")
    a = ap.parse_args(argv)
    root = repo_root()
    run = a.run or (root / ".data" / "artifacts" / PIPELINE / "current")
    files = build(build_release(run.resolve()), root)
    if a.out.exists():
        shutil.rmtree(a.out)
    a.out.mkdir(parents=True)
    for name, data in files.items():
        (a.out / name).write_bytes(data)
    print(json.dumps({n: len(d) for n, d in sorted(files.items())}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

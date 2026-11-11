"""ClinicalTrials.gov bulk download -> evidence candidates (spec model-kit, milestone M2).

Reads the official bulk file (`ctg-studies.json.zip`: one JSON record per study, the same record
format as the study endpoint of the data API) from disk, keeps the studies with posted results that
have a PK outcome measure and name a drug of the pool, and reads each (study, drug) pair with the
two independent readers. Build-time code, no network. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from janus_pipelines.modelkit import reader_a, reader_b
from janus_pipelines.modelkit.model import Candidate, ReaderStats
from janus_pipelines.modelkit.pairing import Paired, pair
from janus_pipelines.modelkit.resolver import IdentityTable

_RESULTS = b'"resultsSection"'
_MAX_MEMBER = 200_000_000  # bytes; a single study record is far smaller


def iter_result_studies(zip_path: Path, counts: Counter[str]) -> Iterator[dict[str, Any]]:
    """Every study record of the bulk file that has posted results with outcome measures."""
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not info.filename.endswith(".json") or info.file_size > _MAX_MEMBER:
                continue
            counts["studies"] += 1
            raw = zf.read(info)
            if _RESULTS not in raw:
                continue
            counts["studies_with_results"] += 1
            study = json.loads(raw)
            if "outcomeMeasuresModule" not in study.get("resultsSection", {}):
                continue
            yield study


def has_pk_outcome(study: dict[str, Any]) -> bool:
    measures = study["resultsSection"]["outcomeMeasuresModule"].get("outcomeMeasures", [])
    return any(reader_a.parameter_of(m.get("title", "")) is not None for m in measures)


def study_drugs(study: dict[str, Any], table: IdentityTable) -> list[str]:
    """Pool drugs named by the interventions, the arm groups or the titles of the record."""
    proto = study["protocolSection"]
    parts: list[str] = []
    ident = proto.get("identificationModule", {})
    parts += [ident.get("briefTitle", ""), ident.get("officialTitle", "")]
    arms = proto.get("armsInterventionsModule", {})
    for i in arms.get("interventions", []):
        parts.append(i.get("name", ""))
        parts += i.get("otherNames", [])
    for g in arms.get("armGroups", []):
        parts += [g.get("label", ""), g.get("description", "")]
    return table.drugs_in(" . ".join(parts))


def read_bulk(
    zip_path: Path,
    table: IdentityTable,
    stats: dict[str, ReaderStats],
    counts: Counter[str],
) -> tuple[list[Paired], list[Candidate], dict[str, set[str]]]:
    """Pairs of the two readers for every (study, drug); candidates only reader B found; the studies
    kept per drug."""
    pairs: list[Paired] = []
    only_b: list[Candidate] = []
    kept: dict[str, set[str]] = {}
    for study in iter_result_studies(zip_path, counts):
        if not has_pk_outcome(study):
            continue
        counts["studies_with_pk_outcome"] += 1
        drugs = study_drugs(study, table)
        if not drugs:
            continue
        counts["studies_naming_a_pool_drug"] += 1
        nct = study["protocolSection"]["identificationModule"]["nctId"]
        for key in drugs:
            a_rows = reader_a.read_ctgov(study, key, table, stats["a"])
            b_rows = reader_b.read_ctgov(study, key, table, stats["b"])
            if not a_rows and not b_rows:
                continue
            kept.setdefault(key, set()).add(nct)
            p, left = pair(a_rows, b_rows)
            pairs += p
            only_b += left
    return pairs, only_b, kept

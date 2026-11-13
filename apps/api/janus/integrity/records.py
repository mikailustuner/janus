"""Evidence records: ids, construction and validation (evidence-integrity design §3.1, §4.5)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from janus.integrity.freshness import parse_snapshot_date
from janus.integrity.model import (
    DATA_STORAGE,
    DOI_RE,
    ID_MAX,
    ID_RE,
    KINDS,
    REGIONS,
    URL_RE,
    EvidenceRecord,
    SourceInfo,
)


class RecordError(ValueError):
    """A record cannot be stored. `code` is fixed; `record_id` names the record, never a value."""

    def __init__(self, code: str, record_id: str = "") -> None:
        super().__init__(f"{code}: {record_id}" if record_id else code)
        self.code = code
        self.record_id = record_id


_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


def normalise_doi(value: str) -> str | None:
    """Same rule as `pipelines/janus_pipelines/jobs/retractions.py`: lower case, no prefix."""
    text = value.strip()
    changed = True
    while changed:
        changed = False
        for prefix in _DOI_PREFIXES:
            if text.lower().startswith(prefix):
                text = text[len(prefix) :].strip()
                changed = True
    text = text.lower()
    return text if DOI_RE.fullmatch(text) else None


def make_id(kind: str, source_id: str, key: str | None = None) -> str:
    value = f"{kind}:{source_id}" + (f":{key}" if key else "")
    if len(value) > ID_MAX or ID_RE.fullmatch(value) is None:
        raise RecordError("bad_id")
    return value


def record_from_evidence_source(
    evidence: Mapping[str, Any],
    manifest: Mapping[str, Any],
    sources: Mapping[str, SourceInfo],
) -> EvidenceRecord:
    """`dataset:<source_id>` from the `evidence_source.json` of a pipeline run."""
    source_id = str(evidence.get("source_id", ""))
    rid = make_id("dataset", source_id)
    try:
        snapshot = parse_snapshot_date(str(evidence.get("snapshot_date", "")))
    except ValueError as exc:
        raise RecordError("missing_snapshot_date", rid) from exc
    doi_raw = evidence.get("doi")
    doi = None
    if doi_raw:
        doi = normalise_doi(str(doi_raw))
        if doi is None:
            raise RecordError("bad_doi", rid)
    info = sources.get(source_id)
    region = evidence.get("region")
    return EvidenceRecord(
        id=rid,
        kind="dataset",
        source_id=source_id,
        # Derived runs (the model kit) name no URL of their own: the registry's first URL stands in.
        source_url=str(evidence.get("source_url") or (info.url if info else None) or ""),
        license=str(evidence.get("license") or ""),
        region=str(region) if region else None,
        snapshot_date=snapshot,
        snapshot_is_retrieval_time=bool(manifest.get("snapshot_date_is_retrieval_time")),
        doi=doi,
        title=info.name if info else None,
    )


def records_from_papers(
    rows: Iterable[Mapping[str, str]], sources: Mapping[str, SourceInfo]
) -> list[EvidenceRecord]:
    """`paper:<source_id>:<key>` from `data/evidence_papers.csv` (DP13)."""
    out: list[EvidenceRecord] = []
    for row in rows:
        source_id = (row.get("source_id") or "").strip()
        key = (row.get("key") or "").strip()
        rid = make_id("paper", source_id, key)
        doi = normalise_doi(row.get("doi") or "")
        if doi is None:
            raise RecordError("bad_doi", rid)
        info = sources.get(source_id)
        if info is None:
            raise RecordError("unknown_source", rid)
        try:
            verified = dt.date.fromisoformat((row.get("verified_on") or "").strip())
        except ValueError as exc:
            raise RecordError("missing_snapshot_date", rid) from exc
        out.append(
            EvidenceRecord(
                id=rid,
                kind="paper",
                source_id=source_id,
                source_url=f"https://doi.org/{doi}",
                license=info.license or "",
                region=info.region,
                snapshot_date=verified,
                snapshot_is_retrieval_time=False,
                doi=doi,
                title=(row.get("title") or "").strip() or None,
            )
        )
    return out


def _find_cycle(graph: Mapping[str, Sequence[str]]) -> str | None:
    """An id on a basis cycle, or None. Iterative depth-first search."""
    state: dict[str, int] = {}  # 1 = on the stack, 2 = done
    for start in sorted(graph):
        if state.get(start):
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        state[start] = 1
        while stack:
            node, i = stack[-1]
            children = graph.get(node, ())
            if i < len(children):
                stack[-1] = (node, i + 1)
                child = children[i]
                st = state.get(child)
                if st == 1:
                    return child
                if st is None and child in graph:
                    state[child] = 1
                    stack.append((child, 0))
            else:
                state[node] = 2
                stack.pop()
    return None


def validate_records(
    new: Sequence[EvidenceRecord],
    known: Mapping[str, Sequence[str]],
    sources: Mapping[str, SourceInfo],
) -> None:
    """Raise `RecordError` for the first defect; nothing is stored by the caller then.

    `known` maps the ids already stored to their basis ids, so a basis may point to a record
    that another spec registered.
    """
    seen: set[str] = set()
    for r in new:
        rid = r.id
        if len(rid) > ID_MAX or ID_RE.fullmatch(rid) is None:
            raise RecordError("bad_id", rid[:ID_MAX])
        if rid in seen:
            raise RecordError("duplicate_id", rid)
        seen.add(rid)
        if r.kind not in KINDS:
            raise RecordError("unknown_kind", rid)
        if not r.source_url or URL_RE.fullmatch(r.source_url) is None:
            raise RecordError("missing_source_url", rid)
        if not r.license or not r.license.strip():
            raise RecordError("missing_license", rid)
        if not isinstance(r.snapshot_date, dt.date):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise RecordError("missing_snapshot_date", rid)
        if r.region is not None and r.region not in REGIONS:
            raise RecordError("bad_region", rid)
        if r.doi is not None and (DOI_RE.fullmatch(r.doi) is None or r.doi != r.doi.lower()):
            raise RecordError("bad_doi", rid)
        info = sources.get(r.source_id)
        if info is None:
            raise RecordError("unknown_source", rid)
        if info.storage in DATA_STORAGE and info.cadence_days is None:
            raise RecordError("no_cadence", rid)
        if r.kind == "rule" and not r.basis:
            raise RecordError("rule_without_basis", rid)
    graph: dict[str, tuple[str, ...]] = {k: tuple(v) for k, v in known.items()}
    graph.update({r.id: tuple(r.basis) for r in new})
    for r in new:
        for b in r.basis:
            if b == r.id:
                raise RecordError("basis_cycle", r.id)
            if b not in graph:
                raise RecordError("unknown_basis", r.id)
    cyc = _find_cycle(graph)
    if cyc is not None:
        raise RecordError("basis_cycle", cyc)

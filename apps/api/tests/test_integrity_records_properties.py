"""Evidence records (evidence-integrity design §3.1, §4.5): P13 (pure), P14 (pure)."""

from __future__ import annotations

import datetime as dt
from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.integrity.model import KINDS, EvidenceRecord
from janus.integrity.records import (
    RecordError,
    make_id,
    normalise_doi,
    record_from_evidence_source,
    records_from_papers,
    validate_records,
)
from tests.integrity_strategies import SOURCE_IDS, SOURCES, dois

SOURCES_WITH_GAP = {
    **SOURCES,
    "s_nocadence": SOURCES["s_weekly"].__class__("s_nocadence", "No cadence", "cache", None),
}


@st.composite
def valid_sets(draw: st.DrawFn) -> list[EvidenceRecord]:
    n = draw(st.integers(1, 7))
    out: list[EvidenceRecord] = []
    for i in range(n):
        basis = tuple(
            draw(st.lists(st.sampled_from([r.id for r in out]), max_size=2, unique=True))
            if out
            else []
        )
        kind = draw(st.sampled_from([k for k in KINDS if k != "rule" or basis]))
        sid = draw(st.sampled_from(SOURCE_IDS))
        out.append(
            EvidenceRecord(
                id=make_id(kind, sid, f"k{i}"),
                kind=kind,
                source_id=sid,
                source_url="https://example.org/x",
                license="CC0 1.0",
                region=draw(st.sampled_from([None, "TR", "EU", "US"])),
                snapshot_date=dt.date(2026, 1, 1),
                snapshot_is_retrieval_time=False,
                doi=draw(st.one_of(st.none(), dois())),
                basis=basis,
            )
        )
    return out


DEFECTS = [
    "duplicate_id",
    "bad_id",
    "unknown_kind",
    "missing_source_url",
    "missing_license",
    "missing_snapshot_date",
    "bad_doi",
    "unknown_source",
    "no_cadence",
    "unknown_basis",
    "basis_cycle",
    "rule_without_basis",
]


def _inject(records: list[EvidenceRecord], defect: str) -> list[EvidenceRecord]:
    recs = list(records)
    r = recs[0]
    if defect == "duplicate_id":
        recs.append(r)
    elif defect == "bad_id":
        recs[0] = replace(r, id="Not An Id")
    elif defect == "unknown_kind":
        recs[0] = replace(r, kind="blog")
    elif defect == "missing_source_url":
        recs[0] = replace(r, source_url="")
    elif defect == "missing_license":
        recs[0] = replace(r, license="  ")
    elif defect == "missing_snapshot_date":
        recs[0] = replace(r, snapshot_date=None)  # type: ignore[arg-type]
    elif defect == "bad_doi":
        recs[0] = replace(r, doi="10.1000/UPPER")
    elif defect == "unknown_source":
        recs[0] = replace(r, source_id="s_missing")
    elif defect == "no_cadence":
        recs[0] = replace(r, source_id="s_nocadence")
    elif defect == "unknown_basis":
        recs[0] = replace(r, basis=("dataset:s_weekly:absent",))
    elif defect == "basis_cycle":
        if len(recs) == 1 or (defect == "basis_cycle" and not recs[-1].id):
            recs[0] = replace(r, basis=(r.id,))
        else:
            last = recs[-1]
            recs[0] = replace(r, basis=(*r.basis, last.id)) if last.id != r.id else r
            recs[-1] = replace(last, basis=(*last.basis, r.id))
    elif defect == "rule_without_basis":
        recs[0] = replace(r, kind="rule", basis=())
    return recs


@given(valid_sets())
def test_p13_valid_sets_are_accepted(recs: list[EvidenceRecord]) -> None:
    validate_records(recs, {}, SOURCES_WITH_GAP)


@given(valid_sets(), st.sampled_from(DEFECTS))
def test_p13_single_defect_gives_its_code(recs: list[EvidenceRecord], defect: str) -> None:
    """Feature: evidence-integrity, Property P13 (pure part) (Req 4.1, 4.4, 4.5, 2.1)."""
    # Make the id of record 0 distinct from others so only the injected defect is present.
    recs = [replace(recs[0], basis=()), *recs[1:]] if defect != "basis_cycle" else recs
    broken = _inject(recs, defect)
    with pytest.raises(RecordError) as exc:
        validate_records(broken, {}, SOURCES_WITH_GAP)
    assert exc.value.code == defect


def test_p13_cadence_only_for_data_sources() -> None:
    cited = EvidenceRecord(
        id=make_id("paper", "s_cited", "a"),
        kind="paper",
        source_id="s_cited",
        source_url="https://doi.org/10.1000/a",
        license="L",
        region=None,
        snapshot_date=dt.date(2026, 1, 1),
        snapshot_is_retrieval_time=False,
        doi="10.1000/a",
    )
    validate_records([cited], {}, SOURCES)


def test_p13_basis_may_point_to_stored_record() -> None:
    rule = EvidenceRecord(
        id="rule:s_weekly:1",
        kind="rule",
        source_id="s_weekly",
        source_url="https://example.org/r",
        license="L",
        region=None,
        snapshot_date=dt.date(2026, 1, 1),
        snapshot_is_retrieval_time=False,
        basis=("dataset:s_weekly",),
    )
    validate_records([rule], {"dataset:s_weekly": ()}, SOURCES)
    with pytest.raises(RecordError) as exc:
        validate_records([rule], {"dataset:s_weekly": ("rule:s_weekly:1",)}, SOURCES)
    assert exc.value.code == "basis_cycle"


@given(
    st.sampled_from(["dataset", "paper", "rule"]),
    st.sampled_from(SOURCE_IDS),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_.-", min_size=1, max_size=12),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_.-", min_size=1, max_size=12),
)
def test_p14_ids_are_deterministic_and_injective(kind: str, sid: str, k1: str, k2: str) -> None:
    """Feature: evidence-integrity, Property P14 (pure part) (Req 4.2, 4.3)."""
    assert make_id(kind, sid, k1) == make_id(kind, sid, k1)
    assert (make_id(kind, sid, k1) == make_id(kind, sid, k2)) == (k1 == k2)
    assert make_id(kind, sid) != make_id(kind, sid, k1)


@given(
    st.sampled_from(SOURCE_IDS),
    st.text(alphabet="0123456789abcdef", min_size=4, max_size=12),
    st.dates(dt.date(2020, 1, 1), dt.date(2030, 1, 1)),
    st.one_of(st.none(), dois()),
)
def test_p14_dataset_id_ignores_run_and_date(
    sid: str, run: str, day: dt.date, doi: str | None
) -> None:
    ev = {
        "source_id": sid,
        "source_url": "https://example.org",
        "license": "L",
        "snapshot_date": day.isoformat(),
        "run_id": run,
        "doi": doi,
        "region": None,
    }
    a = record_from_evidence_source(ev, {"snapshot_date_is_retrieval_time": False}, SOURCES)
    b = record_from_evidence_source(
        {**ev, "run_id": run + "x", "snapshot_date": f"{day.isoformat()}T01:02:03+00:00"},
        {"snapshot_date_is_retrieval_time": True},
        SOURCES,
    )
    assert a.id == b.id == f"dataset:{sid}"
    assert a.snapshot_date == b.snapshot_date == day


def test_papers_csv_rows() -> None:
    rows = [
        {
            "key": "e100499",
            "doi": "https://doi.org/10.1136/BMJ-2025-100499",
            "source_id": "s_cited",
            "title": "T",
            "verified_on": "2026-11-07",
            "note": "",
        }
    ]
    (rec,) = records_from_papers(rows, SOURCES)
    assert rec.id == "paper:s_cited:e100499"
    assert rec.doi == "10.1136/bmj-2025-100499"
    assert rec.source_url == "https://doi.org/10.1136/bmj-2025-100499"
    with pytest.raises(RecordError):
        records_from_papers([{**rows[0], "doi": "nope"}], SOURCES)


def test_doi_normalisation_matches_pipeline_vectors() -> None:
    assert (
        normalise_doi("  https://doi.org/10.1007/S41999-025-01215-X ")
        == "10.1007/s41999-025-01215-x"
    )
    assert normalise_doi("DOI:10.1000/AbC") == "10.1000/abc"
    assert normalise_doi("not a doi") is None


def test_dataset_record_takes_the_registry_url_when_the_run_has_none() -> None:
    """A derived pipeline run (model kit) writes no source URL; the record takes the registry's
    first URL, and is still refused when the registry has none either."""
    from janus.integrity.model import SourceInfo

    ev = {
        "source_id": "derived",
        "source_url": "",
        "license": "L",
        "snapshot_date": "2026-11-11",
        "run_id": "r",
        "doi": None,
        "region": None,
    }
    with_url = {
        "derived": SourceInfo("derived", "Derived", "cache", 90, url="https://example.org/a")
    }
    rec = record_from_evidence_source(ev, {}, with_url)
    assert rec.source_url == "https://example.org/a"
    validate_records([rec], {}, with_url)
    without = {"derived": SourceInfo("derived", "Derived", "cache", 90)}
    with pytest.raises(RecordError, match="missing_source_url"):
        validate_records([record_from_evidence_source(ev, {}, without)], {}, without)
    own = record_from_evidence_source({**ev, "source_url": "https://example.org/own"}, {}, with_url)
    assert own.source_url == "https://example.org/own"


def test_registry_reads_the_first_url() -> None:
    from janus.integrity.registry import parse_sources

    text = '[[sources]]\nid = "a"\nname = "A"\nstorage = "cache"\nurls = ["https://x.org/1", "https://x.org/2"]\n'
    assert parse_sources(text)["a"].url == "https://x.org/1"
    assert (
        parse_sources(text.replace('urls = ["https://x.org/1", "https://x.org/2"]\n', ""))["a"].url
        is None
    )

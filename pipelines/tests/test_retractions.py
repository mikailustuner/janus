"""Tests for the retractions job (P14, P15, P16 and examples). Recorded responses only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.manifest import Outcome
from janus_pipelines.core.registry import load_registry
from janus_pipelines.core.runner import RawInput, RunContext, run_job
from janus_pipelines.jobs.retractions import (
    NOTICE_STATUS,
    SEVERITY,
    Payload,
    Previous,
    Response,
    RetractionsJob,
    Status,
    effective,
    normalise_doi,
    status_from_notices,
)
from tests.stub_job import FIXED_NOW

REPO = Path(__file__).resolve().parents[2]
NOTICE_TYPES = st.one_of(
    st.sampled_from(sorted(NOTICE_STATUS)),
    st.text(alphabet="abcdefghij_", min_size=1, max_size=12),  # unknown types
)


@given(st.lists(NOTICE_TYPES, max_size=8), st.data())
def test_most_severe_notice_wins(types: list[str], data: st.DataObject) -> None:
    """Feature: data-pipelines, Property P14 — Validates: Req 9.2, 9.3.

    The status is the most severe notice whatever their order; no notice gives ok;
    adding a retraction notice always gives retracted.
    """
    status = status_from_notices(types)
    shuffled = data.draw(st.permutations(types))
    assert status_from_notices(shuffled) == status
    expected = max(
        (NOTICE_STATUS.get(t, Status.CORRECTED) for t in types),
        key=SEVERITY.__getitem__,
        default=Status.OK,
    )
    assert status == expected
    position = data.draw(st.integers(0, len(types)))
    with_retraction = [*types[:position], "retraction", *types[position:]]
    assert status_from_notices(with_retraction) is Status.RETRACTED


CHECKS = st.sampled_from(list(Status))


@given(st.lists(CHECKS, min_size=1, max_size=12))
def test_failed_check_never_unretracts(history: list[Status]) -> None:
    """Feature: data-pipelines, Property P15 — Validates: Req 9.4, 9.5.

    Folding any history of checks: after a completed `retracted` check, any run of failed
    (`unknown`) checks keeps `retracted`; `unknown` never becomes `ok`.
    """
    last: Status | None = None
    for check in history:
        eff = effective(last, check)
        if check is Status.UNKNOWN:
            assert eff is not Status.OK
            if last is Status.RETRACTED:
                assert eff is Status.RETRACTED
            else:
                assert eff is Status.UNKNOWN
        else:
            assert eff is check
            last = check


def _doi(registrant: int, suffix: str) -> str:
    return f"10.{registrant}/{suffix}"


DOI = st.builds(
    _doi,
    st.integers(1000, 999999999),
    st.text(alphabet="abcdefXYZ0123456789-._;()/:", min_size=1, max_size=20).filter(
        lambda s: not any(c.isspace() for c in s)
    ),
)
PREFIX = st.sampled_from(
    ["", "doi:", "DOI:", "https://doi.org/", "HTTPS://DOI.ORG/", "http://dx.doi.org/", " doi: "]
)


@given(DOI, PREFIX, st.booleans())
def test_doi_normalisation(doi: str, prefix: str, upper: bool) -> None:
    """Feature: data-pipelines, Property P16 — Validates: Req 9.1.

    Normalisation is idempotent and ignores case and the allowed prefixes.
    """
    variant = prefix + (doi.upper() if upper else doi)
    n = normalise_doi(variant)
    assert n is not None
    assert n == normalise_doi(doi) == doi.lower()
    assert normalise_doi(n) == n


def test_not_a_doi() -> None:
    assert normalise_doi("https://example.org/x") is None
    assert normalise_doi("10.12/x") is None


WAKEFIELD = "10.1016/s0140-6736(97)11096-0"
RECORDED = {
    "status": "ok",
    "message": {
        "DOI": WAKEFIELD,
        "updated-by": [
            {
                "DOI": "10.1016/s0140-6736(04)15715-2",
                "type": "correction",
                "label": "Correction",
                "source": "retraction-watch",
                "updated": {"date-time": "2004-03-06T00:00:00Z"},
                "record-id": "17269",
            },
            {
                "DOI": "10.1016/s0140-6736(10)60175-4",
                "type": "retraction",
                "label": "Retraction",
                "source": "retraction-watch",
                "updated": {"date-time": "2010-02-06T00:00:00Z"},
                "record-id": "4036",
            },
        ],
    },
}


def _raw(
    responses: dict[str, Response], dois: tuple[str, ...], previous: Any = None
) -> RawInput[Payload]:
    return RawInput(
        payload=Payload(dois=dois, responses=responses, previous=previous or {}, checked_at="t"),
        source_urls=("https://api.crossref.org/works/",),
        source_sha256="x" * 64,
        retrieved_at=FIXED_NOW,
        snapshot_date=FIXED_NOW.isoformat(),
        snapshot_date_is_retrieval_time=True,
    )


def test_recorded_retraction_watch_response() -> None:
    """Validates: Req 9.2, 9.7 — shape of a real Crossref response (fetched 2026-11-07)."""
    resp = Response(status=200, body=json.dumps(RECORDED).encode())
    result = RetractionsJob().parse(
        _raw({WAKEFIELD: resp}, ("https://doi.org/" + WAKEFIELD.upper(),))
    )
    row = result.rows[0]
    assert row["check_status"] == row["effective_status"] == "retracted"
    notices = row["notices"]
    assert isinstance(notices, list)
    retraction = next(n for n in notices if isinstance(n, dict) and n["type"] == "retraction")
    assert retraction["source"] == "retraction-watch"
    assert retraction["notice_doi"] == "10.1016/s0140-6736(10)60175-4"
    assert retraction["date"] == "2010-02-06"


def test_not_found_and_failure_are_unknown() -> None:
    """Validates: Req 9.4, 9.5."""
    a, b, c = "10.1000/a", "10.1000/b", "10.1000/c"
    previous = {
        b: Previous(last_completed=Status.RETRACTED, effective=Status.RETRACTED),
        c: Previous(last_completed=Status.OK, effective=Status.OK),
    }
    responses = {
        a: Response(status=404, body=b"Resource not found."),
        b: Response(status=None, body=None, error="timeout"),
        c: Response(status=None, body=None, error="timeout"),
    }
    result = RetractionsJob().parse(_raw(responses, (a, b, c, "nonsense", a), previous))
    by = {r["doi"]: r for r in result.rows}
    assert by[a]["effective_status"] == "unknown" and by[a]["reason"] == "not_found"
    assert by[b]["check_status"] == "unknown"
    assert by[b]["effective_status"] == "retracted"
    assert by[b]["last_completed_status"] == "retracted"
    assert by[c]["effective_status"] == "unknown"
    assert result.excluded == {"invalid_doi": 1, "duplicate_doi": 1}
    assert {"doi": c, "from": "ok", "to": "unknown"} in result.changes
    assert result.review_reasons == []


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(
        data_dir=tmp_path / "data_dir",
        repo_root=tmp_path / "repo",
        registry=load_registry(REPO / "pipelines" / "sources.toml"),
        code_version="test",
        now=lambda: FIXED_NOW,
        is_ignored=lambda _p: True,
    )


def test_unretraction_needs_review(tmp_path: Path) -> None:
    """Validates: Req 9.6 — a change away from retracted is not promoted automatically."""
    ok = {"status": "ok", "message": {"DOI": WAKEFIELD}}
    previous = {WAKEFIELD: Previous(last_completed=Status.RETRACTED, effective=Status.RETRACTED)}
    raw = _raw({WAKEFIELD: Response(200, json.dumps(ok).encode())}, (WAKEFIELD,), previous)
    result = run_job(RetractionsJob(), _ctx(tmp_path), raw)
    assert result.outcome is Outcome.NEEDS_REVIEW
    assert "from retracted to ok" in result.manifest.review_reasons[0]
    assert result.manifest.changes == [{"doi": WAKEFIELD, "from": "retracted", "to": "ok"}]


def test_idempotent_with_same_responses() -> None:
    """Re-running with unchanged responses gives identical rows (evidence-integrity)."""
    resp = {WAKEFIELD: Response(status=200, body=json.dumps(RECORDED).encode())}
    a = RetractionsJob().parse(_raw(resp, (WAKEFIELD,)))
    b = RetractionsJob().parse(_raw(resp, (WAKEFIELD,)))
    assert a.rows == b.rows

"""FAERS citation: locator, the finding hook, no number below the threshold (design §10: P26, P27).

Owner decision 2026-11-08 (DP12): one dataset-level record `dataset:faers` plus a deterministic
locator; no per-pair records, no loader that writes records.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.cascades.engine import evaluate
from janus.cascades.model import EngineItem, RuleBase
from janus.integrity.citability import cite
from janus.integrity.model import EvidenceRecord, IntegritySnapshot
from janus.memory import service
from janus.memory.evidence import (
    FAERS_EVIDENCE_ID,
    EventRef,
    Locator,
    LocatorError,
    faers_locator,
    parse_locator,
)
from janus.memory.model import RESPONSE_REGIONS
from janus.memory.reader import CountsHolder
from janus.memory.schemas import PairIn
from tests.cascades_strategies import TODAY, cascade_snapshot, engine_items, rule_bases
from tests.memory_counts import make_counts, mk
from tests.test_faers_build_properties import ReportFact
from tests.test_memory_service_properties import ctx

keys = st.one_of(
    st.integers(1, 9_999_999_999).map(lambda n: f"Q{n}"),
    st.integers(1, 999_999).map(lambda n: f"J{n}"),
)
event_keys = st.from_regex(r"[a-z0-9][a-z0-9_.-]{0,39}", fullmatch=True)
pts = st.text(min_size=1, max_size=60).filter(lambda t: t.strip() == t or True)
events = st.one_of(
    st.just(EventRef()),
    event_keys.map(lambda k: EventRef(key=k)),
    pts.map(lambda p: EventRef(pt=p)),
)
scopes = st.sampled_from(["suspect", "any"])
regions = st.sampled_from(list(RESPONSE_REGIONS))


@settings(max_examples=400, deadline=None)
@given(st.lists(keys, min_size=1, max_size=20), events, regions, scopes)
def test_locator_round_trip(ings: list[str], event: EventRef, region: str, scope: str) -> None:
    """Feature: collective-memory, Property P27 — Validates: Req 10.3."""
    text = faers_locator(ings, event, region, scope)
    assert parse_locator(text) == Locator(tuple(sorted(set(ings))), event, region, scope)
    assert faers_locator(list(reversed(ings)), event, region, scope) == text  # order never matters
    assert text.startswith("faers:ingredient=") and "\n" not in text
    # nothing but the four parts: PT text with separators is percent-encoded
    assert text.count(";") == 3


@settings(max_examples=200, deadline=None)
@given(
    st.lists(keys, min_size=1, max_size=3),
    st.sampled_from(
        [
            "",
            "x",
            "faers:",
            "faers:ingredient=Q1",
            "faers:ingredient=Q1;event=;region=ALL",
            "faers:ingredient=q1;event=;region=ALL;scope=any",
            "faers:ingredient=Q1;event=;region=XX;scope=any",
            "faers:ingredient=Q1;event=;region=ALL;scope=all",
            "faers:ingredient=Q2,Q1;event=;region=ALL;scope=any",
            "faers:ingredient=Q1;event=pt:%zz;region=ALL;scope=any",
            "faers:ingredient=Q1;event=pt:a b;region=ALL;scope=any",
            "faers:ingredient=Q1;event=Bad Key;region=ALL;scope=any",
            "other:ingredient=Q1;event=;region=ALL;scope=any",
        ]
    ),
)
def test_malformed_locators_are_rejected(_ings: list[str], text: str) -> None:
    """Feature: collective-memory, Property P27 — Validates: Req 10.3."""
    with pytest.raises(LocatorError):
        parse_locator(text)


def test_locator_inputs_are_checked() -> None:
    for bad in (
        lambda: faers_locator([], EventRef(), "ALL", "any"),
        lambda: faers_locator(["x"], EventRef(), "ALL", "any"),
        lambda: faers_locator(["Q1"], EventRef(key="a", pt="b"), "ALL", "any"),
        lambda: faers_locator(["Q1"], EventRef(pt=""), "ALL", "any"),
        lambda: faers_locator(["Q1"], EventRef(), "FR", "any"),
        lambda: faers_locator(["Q1"], EventRef(), "ALL", "all"),
    ):
        with pytest.raises(LocatorError):
            bad()
    assert faers_locator(["Q1"], EventRef(pt="Oedema peripheral"), "US", "any") == (
        "faers:ingredient=Q1;event=pt:Oedema%20peripheral;region=US;scope=any"
    )


def test_the_citation_does_not_depend_on_the_build(tmp_path: Path) -> None:
    """Feature: collective-memory, Property P27 — Validates: Req 10.3 (no build id or date)."""
    facts = [ReportFact("100001", "2026Q3", "US", (("PS", ("ASPIRIN",)),), ("Cough",))]
    a, b = tmp_path / "a", tmp_path / "b"
    first = make_counts(a, facts)
    second = make_counts(b, facts)
    assert first.build_id != second.build_id
    out: list[dict[str, str]] = []
    for d in (a, b):
        with CountsHolder(d).current().session() as s:
            res = service.pair(s, mk(PairIn, ingredient="Q1", event={"key": "cough"}), ctx())
        assert res.citation is not None
        out.append(res.citation.model_dump())
    assert out[0] == out[1] and out[0]["evidence_id"] == FAERS_EVIDENCE_ID


# --- the finding hook (cascade-engine DP22) ----------------------------------------------------


def with_faers_record(snap: IntegritySnapshot) -> IntegritySnapshot:
    record = EvidenceRecord(
        id=FAERS_EVIDENCE_ID,
        kind="dataset",
        source_id="s_cited",
        source_url="https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html",
        license="CC0 1.0",
        region="US",
        snapshot_date=dt.date(2026, 10, 28),
        snapshot_is_retrieval_time=False,
        doi=None,
        locator=None,
        title=None,
        basis=(),
    )
    return IntegritySnapshot({**snap.records, FAERS_EVIDENCE_ID: record}, snap.states, snap.sources)


@settings(max_examples=60, deadline=None)
@given(rb=rule_bases(), items=engine_items())
def test_findings_cite_the_dataset_with_a_locator(rb: RuleBase, items: list[EngineItem]) -> None:
    """Feature: collective-memory, Properties P26/P27 (hook) — Validates: Req 10.3, 10.4.
    With a Janus key on a rule and `dataset:faers` registered, the finding cites it and carries the
    locator of its index ingredient; without the record neither appears and the id is reported as
    not registered; with no mapping nothing changes at all.
    """
    plain = cascade_snapshot(rb)
    registered = with_faers_record(plain)
    mapping = {r.position: "cough" for r in rb.rules}
    rb_keys = dataclasses.replace(rb, faers_event_keys=mapping)

    base = evaluate(items, rb, registered, TODAY)
    assert all(f.faers_locator is None for f in base.findings)
    assert all(FAERS_EVIDENCE_ID not in f.evidence_ids for f in base.findings)

    with_record = evaluate(items, rb_keys, registered, TODAY)
    assert len(with_record.findings) == len(base.findings)
    for f, g in zip(base.findings, with_record.findings, strict=True):
        assert FAERS_EVIDENCE_ID in g.evidence_ids
        assert g.faers_locator == faers_locator(
            (g.index.key,), EventRef(key="cough"), "ALL", "suspect"
        )
        assert dataclasses.replace(g, evidence_ids=f.evidence_ids, faers_locator=None) == f

    without = evaluate(items, rb_keys, plain, TODAY)
    for g in without.findings:
        assert FAERS_EVIDENCE_ID not in g.evidence_ids and g.faers_locator is None
        assert (FAERS_EVIDENCE_ID, "not_registered") in g.excluded_evidence
    assert cite(plain, [FAERS_EVIDENCE_ID]).kept == ()
    assert cite(registered, [FAERS_EVIDENCE_ID]).kept == (FAERS_EVIDENCE_ID,)


# --- no number below the threshold -------------------------------------------------------------


@settings(max_examples=12, deadline=None)
@given(st.integers(0, 6), st.integers(0, 6))
def test_no_estimate_below_three_reports(n_both: int, n_other: int) -> None:
    """Feature: collective-memory, Property P26 — Validates: Req 1.3, 8.8, 10.3."""
    facts = [
        ReportFact(str(100000 + i), "2026Q3", "US", (("PS", ("ASPIRIN",)),), ("Cough",))
        for i in range(n_both)
    ] + [
        ReportFact(str(200000 + i), "2026Q3", "US", (("PS", ("METFORMIN",)),), ("Rash",))
        for i in range(n_other + 2)
    ]
    with tempfile.TemporaryDirectory() as d:
        make_counts(Path(d), facts)
        with CountsHolder(Path(d)).current().session() as s:
            out = service.pair(s, mk(PairIn, ingredient="Q1", event={"pt": "Cough"}), ctx())
    st_ = out.stats
    assert st_ is not None and out.citation is not None  # coverage sentences cite the dataset too
    assert out.citation.evidence_id == "dataset:faers"
    assert st_.cells.a == n_both
    if n_both < 3:
        assert st_.estimates is None and st_.sensitivity.estimates is None
        assert st_.assessment == ("no_reports" if n_both == 0 else "insufficient_data")
        assert "weak_pattern" not in st_.codes and not st_.evans_met and not st_.ror_signal
        assert "absence_is_not_reassurance" in out.notices
    else:
        assert st_.estimates is not None

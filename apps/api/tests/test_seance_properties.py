"""Séance synthesis and witnesses, pure (séance design §4, §8): P9-P15."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.integrity.citability import verdict_map
from janus.integrity.model import (
    EvidenceRecord,
    IntegritySnapshot,
    IntegrityState,
    SourceInfo,
    Status,
)
from janus.memory.reader import RawCells
from janus.seance.catalogue import Claim, PresentLink, Study, load_catalogue
from janus.seance.model import (
    CONDITIONS,
    WITNESSES,
    Locator,
    PastItem,
    PresentItem,
    ScienceItem,
    Witness,
    silent,
    synthesize,
)
from janus.seance.schemas import SeanceOut
from janus.seance.witnesses import (
    MIN_REPORTS,
    past_witness,
    present_witness,
    science_witness,
)

SUBS = ("henna", "vinegar", "honey")
LOC = Locator("canon.b2.h0001", "canon.b2.h0001.l1.aaaaaa", 2, None, 1, 2)


def _item(n: int) -> PastItem:
    return PastItem(f"c{n}", LOC, "نص", "text", "use", "passed_both", "pending", True)


@st.composite
def witnesses(draw: st.DrawFn, name: str) -> Witness:
    if draw(st.booleans()):
        items = tuple(_item(i) for i in range(draw(st.integers(1, 3))))
        return Witness(name, items, draw(st.sampled_from(["low", "moderate"])), None)  # type: ignore[arg-type]
    return silent(name, "no_canon_passage")  # type: ignore[arg-type]


@given(witnesses("past"), witnesses("present"), witnesses("science"))
def test_count_equals_non_empty_sections(p: Witness, r: Witness, s: Witness) -> None:
    """P9 (Req 2.2, 2.3): the witness count is the number of non-empty sections, and the
    missing list names exactly the empty ones, in order."""
    out = synthesize("henna", "burn", p, r, s)
    ws = (p, r, s)
    assert out.supporting == sum(1 for w in ws if w.items)
    assert out.missing == tuple(w.name for w in ws if not w.items)
    assert 0 <= out.supporting <= 3


@given(witnesses("past"), witnesses("present"), witnesses("science"), st.sampled_from(WITNESSES))
def test_removing_a_witness_never_raises_the_count(
    p: Witness, r: Witness, s: Witness, drop: str
) -> None:
    """P10 (requirements PBT 3): replacing any witness's data by nothing never increases the
    count."""
    before = synthesize("henna", "burn", p, r, s).supporting
    ws = {"past": p, "present": r, "science": s}
    ws[drop] = silent(drop, "no_canon_passage")  # type: ignore[arg-type]
    after = synthesize("henna", "burn", ws["past"], ws["present"], ws["science"]).supporting
    assert after <= before


def test_response_has_no_merged_score() -> None:
    """P11 (Req 2.2): the response schema has no score, strength or 'proven' field."""
    schema = json.dumps(SeanceOut.model_json_schema()).lower()
    for banned in ("score", "strength", "proven", "overall", "combined", "verdict"):
        assert banned not in schema


def test_witness_invariants_are_enforced() -> None:
    with pytest.raises(ValueError, match="missing reason"):
        Witness("past", (_item(1),), "low", "no_canon_passage")
    with pytest.raises(ValueError, match="needs a missing reason"):
        Witness("past", (), "none", None)
    with pytest.raises(ValueError, match="confidence"):
        Witness("past", (), "low", "no_canon_passage")


# --- past ---------------------------------------------------------------------------------


@st.composite
def claims(draw: st.DrawFn) -> list[Claim]:
    out: list[Claim] = []
    for i in range(draw(st.integers(0, 8))):
        out.append(
            Claim(
                claim_id=f"c{i}",
                substance_id=draw(st.sampled_from(SUBS)),
                condition=draw(st.sampled_from(CONDITIONS)),
                locator=LOC,
                arabic_span="نص",
                machine_translation_en="t",
                use_en="u",
                ai_review=draw(st.sampled_from(["passed_both", "rejected"])),
                expert_review="pending",
                headline_eligible=draw(st.booleans()),
            )
        )
    return out


@given(claims(), st.sampled_from(SUBS), st.sampled_from(CONDITIONS))
def test_past_items_are_reviewed_claims_of_the_pair(cs: list[Claim], sub: str, cond: str) -> None:
    """P12 (Req 1.5, 2.1): the past witness shows only claims of the pair that passed both AI
    passes; without expert review its confidence is never above low."""
    w = past_witness(cs, sub, cond)
    want = {
        c.claim_id
        for c in cs
        if (c.substance_id, c.condition, c.ai_review) == (sub, cond, "passed_both")
    }
    assert {i.claim_id for i in w.items if isinstance(i, PastItem)} == want
    assert w.confidence in (("low",) if want else ("none",))


# --- present ------------------------------------------------------------------------------

LINK = st.builds(
    PresentLink,
    st.just("Q47512"),
    st.sampled_from(["same", "component", "different"]),
    st.just("n"),
)


@st.composite
def cells(draw: st.DrawFn) -> RawCells:
    n = draw(st.integers(10, 10**6))
    exposure = draw(st.integers(0, n))
    event = draw(st.integers(0, n))
    a = draw(st.integers(0, min(exposure, event)))
    if exposure + event - a > n:
        event = a
    return RawCells(n, n, exposure, event, event, a)


@given(st.none() | LINK, st.none() | cells())
def test_present_supports_only_protective_patterns(
    link: PresentLink | None, c: RawCells | None
) -> None:
    """P13 (Req 2.1; light-face Req 1.1): the present witness supports only for a matching
    exposure, at least MIN_REPORTS reports and a ROR interval entirely below 1."""
    w = present_witness(link, c, "2026-10-28" if c else None)
    if w.supports:
        assert link is not None and link.exposure_match != "different"
        assert c is not None and c.a >= MIN_REPORTS
        item = w.items[0]
        assert isinstance(item, PresentItem) and item.ror_ci.high < 1.0
        assert w.confidence == "low"
    if link is None or c is None or (link.exposure_match == "different"):
        assert not w.supports


# --- science ------------------------------------------------------------------------------

TODAY = dt.date(2026, 11, 8)


@st.composite
def studies_and_snapshot(draw: st.DrawFn) -> tuple[list[Study], IntegritySnapshot]:
    studies: list[Study] = []
    records: dict[str, EvidenceRecord] = {}
    states: dict[str, IntegrityState] = {}
    for i in range(draw(st.integers(0, 5))):
        eid = f"paper:seance_science:p{i}"
        doi = f"10.1000/p{i}"
        studies.append(
            Study(
                eid,
                doi,
                "t",
                draw(st.sampled_from(["rct", "in_vitro", "systematic_review"])),
                draw(st.sampled_from(["supports", "mixed", "no_effect"])),
                "f",
            )
        )
        if draw(st.booleans()):
            records[eid] = EvidenceRecord(
                eid, "paper", "seance_science", "u", "L", None, TODAY, False, doi
            )
            status = draw(st.sampled_from(list(Status)))
            states[eid] = IntegrityState(status, status, None, TODAY, "r")
    src = {"seance_science": SourceInfo("seance_science", "n", "cited_only", None)}
    return studies, IntegritySnapshot(records, states, src)


def _science(studies: Sequence[Study], snap: IntegritySnapshot) -> Witness:
    vm = verdict_map(snap) if snap.records else None
    return science_witness(studies, vm, {k: v.status.value for k, v in snap.states.items()})


@given(studies_and_snapshot())
def test_science_never_rests_on_retracted_or_unregistered_papers(
    data: tuple[list[Study], IntegritySnapshot],
) -> None:
    """P14 (Req 4.3): every science item is a registered, non-retracted, supporting study."""
    studies, snap = data
    w = _science(studies, snap)
    for item in w.items:
        assert isinstance(item, ScienceItem)
        eid = item.evidence_id
        assert eid in snap.records
        assert snap.state_of(eid).status is not Status.RETRACTED
    if w.supports:
        assert w.confidence in ("low", "moderate")


@given(studies_and_snapshot(), st.data())
def test_dropping_a_study_never_adds_support(
    data: tuple[list[Study], IntegritySnapshot], d: st.DataObject
) -> None:
    """P15: removing a listed study never turns a silent science witness into a supporting one."""
    studies, snap = data
    before = _science(studies, snap).supports
    if studies:
        k = d.draw(st.integers(0, len(studies) - 1))
        after = _science(studies[:k] + studies[k + 1 :], snap).supports
        assert after <= before


# --- the committed catalogue ----------------------------------------------------------------


def test_every_ancient_claim_locator_resolves() -> None:
    """P16 (requirements PBT 1): every claim's locator resolves to an entry of the package and
    lies inside it; every claim names a known substance (load_catalogue validates both)."""
    cat = load_catalogue()
    assert cat.claims
    for c in cat.claims:
        lo, hi = cat.entries[c.locator.entry_id]
        assert lo <= c.locator.line_start <= c.locator.line_end <= hi
        assert c.substance_id in cat.substances
        assert c.expert_review == "pending"

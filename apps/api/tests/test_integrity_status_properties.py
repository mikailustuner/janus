"""Status merge and validation (evidence-integrity design §4.1): P4 (pure), P5, P6."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.integrity.model import UNCHECKED, IntegrityState, Status
from janus.integrity.status import (
    Incoming,
    InvalidIncomingError,
    incoming_from_row,
    merge_status,
)
from tests.integrity_strategies import REASONS, TODAY, notices, row_for, states_for, valid_rows

COMPLETED = [Status.OK, Status.CORRECTED, Status.EXPRESSION_OF_CONCERN, Status.RETRACTED]


@st.composite
def events(draw: st.DrawFn) -> tuple[str, Incoming | None, Status | None]:
    kind = draw(st.sampled_from(["complete", "failed", "missing"]))
    if kind == "missing":
        return kind, None, None
    if kind == "complete":
        status = draw(st.sampled_from(COMPLETED))
        row = row_for(draw(states_for(status)))
        return kind, incoming_from_row(row), status
    eff = draw(st.sampled_from([Status.UNKNOWN, Status.RETRACTED]))
    row = dict(
        row_for(
            IntegrityState(
                Status.UNKNOWN, Status.UNKNOWN, draw(st.sampled_from(REASONS)), TODAY, None, ()
            )
        )
    )
    row["effective_status"] = eff.value
    return kind, incoming_from_row(row), eff


@given(st.lists(events(), min_size=1, max_size=12))
def test_p5_sticky_retraction(seq: list[tuple[str, Incoming | None, Status | None]]) -> None:
    """Feature: evidence-integrity, Property P5 (Req 1.5)."""
    state: IntegrityState | None = None
    model_status = Status.UNKNOWN
    model_notices: tuple[Any, ...] = ()
    for kind, inc, detail in seq:
        before = model_status
        state = merge_status(state, inc, "run")
        if kind == "complete":
            assert inc is not None and detail is not None
            model_status, model_notices = detail, inc.notices
        elif kind == "failed":
            assert detail is not None
            if before == Status.RETRACTED or detail == Status.RETRACTED:
                model_status = Status.RETRACTED
                if before == Status.RETRACTED:
                    pass  # notices kept
                else:
                    model_notices = ()
            else:
                model_status, model_notices = Status.UNKNOWN, ()
        assert state.status == model_status
        assert state.notices == tuple(model_notices)
        if kind != "complete" and before == Status.RETRACTED:
            assert state.status == Status.RETRACTED
        if kind == "failed":
            assert state.status != Status.OK
            assert state.check_status == Status.UNKNOWN
    if state is not None and all(k == "missing" for k, _, _ in seq):
        assert state == UNCHECKED


@given(st.one_of(st.none(), states_for(Status.RETRACTED)), valid_rows())
def test_p4_merge_is_idempotent(previous: IntegrityState | None, row: dict[str, Any]) -> None:
    """Feature: evidence-integrity, Property P4 (pure part) (Req 1.1, 8.2)."""
    inc = incoming_from_row(row)
    once = merge_status(previous, inc, "r")
    assert merge_status(once, inc, "r") == once


@given(valid_rows())
def test_valid_rows_are_accepted(row: dict[str, Any]) -> None:
    inc = incoming_from_row(row)
    assert inc.doi == row["doi"]


def _mutations(row: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    failed = row["check_status"] == "unknown"
    out.append({**row, "check_status": "fine"})
    out.append({**row, "effective_status": "certain"})
    out.append({**row, "doi": "https://doi.org/10.1000/X"})
    out.append({**row, "checked_at": "not a date"})
    out.append({**row, "notices": "none"})
    if row["check_status"] == "ok":
        out.append({**row, "effective_status": "corrected"})
        out.append({**row, "notices": [{"type": "correction"}]})
        out.append({**row, "reason": "check_failed"})
    elif failed:
        out.append({**row, "reason": None})
        out.append({**row, "reason": "something else"})
        out.append({**row, "effective_status": "ok"})
        out.append({**row, "notices": [{"type": "retraction"}]})
    else:
        out.append({**row, "notices": []})
        out.append({**row, "reason": "check_failed"})
        out.append(
            {**row, "effective_status": "ok" if row["check_status"] != "ok" else "retracted"}
        )
    return out


@given(valid_rows())
def test_p6_malformed_rows_are_refused(row: dict[str, Any]) -> None:
    """Feature: evidence-integrity, Property P6 (Req 1.1, 8.1)."""
    for bad in _mutations(row):
        with pytest.raises(InvalidIncomingError):
            incoming_from_row(bad)


@given(notices())
def test_unknown_notice_type_is_kept_as_other(n: Any) -> None:
    row = row_for(IntegrityState(Status.CORRECTED, Status.CORRECTED, None, TODAY, None, (n,)))
    row = {**row, "notices": [{**row["notices"][0], "type": "Totally New Type!"}]}
    inc = incoming_from_row(row)
    assert inc.notices[0].type == "other"
    assert inc.checked_at == dt.date(2026, 11, 7)

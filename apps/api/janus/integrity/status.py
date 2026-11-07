"""Status rules (evidence-integrity design §4.1, Req 1, 5.1). Pure.

What a status *is* is decided by the `retractions` pipeline from Crossref notices (DP3). This
module validates the rows the pipeline produced and merges them with the stored state, so that
a failed check or a missing row never undoes a retraction (Req 1.5, DP15).
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from janus.integrity.freshness import parse_snapshot_date
from janus.integrity.model import (
    DOI_RE,
    NOTICE_TYPE_RE,
    REASON_RE,
    UNCHECKED,
    IntegrityState,
    Notice,
    Status,
)

SEVERITY: dict[Status, int] = {
    Status.OK: 0,
    Status.CORRECTED: 1,
    Status.EXPRESSION_OF_CONCERN: 2,
    Status.RETRACTED: 3,
}
# Worst first; `unknown` stands outside the severity order and is never treated as `ok`.
ATTENTION_ORDER: tuple[Status, ...] = (
    Status.RETRACTED,
    Status.EXPRESSION_OF_CONCERN,
    Status.UNKNOWN,
    Status.CORRECTED,
    Status.OK,
)


class InvalidIncomingError(ValueError):
    """A `retractions` row cannot be used. `code` is fixed; the message holds no row data."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Incoming:
    doi: str
    check_status: Status
    effective_status: Status
    reason: str | None
    notices: tuple[Notice, ...]
    checked_at: dt.date


def sort_notices(notices: Sequence[Notice]) -> tuple[Notice, ...]:
    """Newest first (date descending, missing dates last), then type, then notice DOI."""
    return tuple(
        sorted(
            notices,
            key=lambda n: (
                n.date is None,
                -(n.date.toordinal() if n.date else 0),
                n.type,
                n.notice_doi or "",
                n.source or "",
            ),
        )
    )


def normalise_notice_type(value: str) -> str:
    t = value.strip().lower().replace("-", "_").replace(" ", "_")
    return t if NOTICE_TYPE_RE.fullmatch(t) else "other"


def _status(value: object) -> Status:
    try:
        return Status(str(value))
    except ValueError as exc:
        raise InvalidIncomingError("bad_status") from exc


def _notice(raw: object) -> Notice:
    if not isinstance(raw, Mapping):
        raise InvalidIncomingError("bad_notice")
    n = cast(Mapping[str, Any], raw)
    doi = n.get("notice_doi")
    if doi is not None and (not isinstance(doi, str) or DOI_RE.fullmatch(doi) is None):
        raise InvalidIncomingError("bad_notice_doi")
    date_raw = n.get("date")
    date: dt.date | None = None
    if date_raw not in (None, ""):
        try:
            date = parse_snapshot_date(str(date_raw))
        except ValueError as exc:
            raise InvalidIncomingError("bad_notice_date") from exc
    source = n.get("source")
    if source is not None and (not isinstance(source, str) or len(source) > 40):
        raise InvalidIncomingError("bad_notice")
    return Notice(normalise_notice_type(str(n.get("type", ""))), source, doi, date)


def validate_incoming(inc: Incoming) -> None:
    """Raise `InvalidIncomingError` unless the row is internally consistent (design §4.1)."""
    check, eff = inc.check_status, inc.effective_status
    if not (eff == check or (check == Status.UNKNOWN and eff == Status.RETRACTED)):
        raise InvalidIncomingError("status_mismatch")
    if check == Status.UNKNOWN:
        if inc.reason is None or REASON_RE.fullmatch(inc.reason) is None:
            raise InvalidIncomingError("bad_reason")
        if inc.notices:
            raise InvalidIncomingError("notices_on_failed_check")
    else:
        if inc.reason is not None:
            raise InvalidIncomingError("reason_on_completed_check")
        if check == Status.OK and inc.notices:
            raise InvalidIncomingError("notices_on_ok")
        if check != Status.OK and not inc.notices:
            raise InvalidIncomingError("missing_notice")


def incoming_from_row(row: Mapping[str, Any]) -> Incoming:
    """Build and validate an `Incoming` from a `retractions` artifact row."""
    doi = row.get("doi")
    if not isinstance(doi, str) or DOI_RE.fullmatch(doi) is None or doi != doi.lower():
        raise InvalidIncomingError("bad_doi")
    raw_notices: object = row.get("notices") or []
    if not isinstance(raw_notices, Sequence) or isinstance(raw_notices, str):
        raise InvalidIncomingError("bad_notice")
    try:
        checked = parse_snapshot_date(str(row.get("checked_at", "")))
    except ValueError as exc:
        raise InvalidIncomingError("bad_checked_at") from exc
    reason = row.get("reason")
    inc = Incoming(
        doi=doi,
        check_status=_status(row.get("check_status")),
        effective_status=_status(row.get("effective_status")),
        reason=None if reason in (None, "") else str(reason),
        notices=sort_notices([_notice(n) for n in cast(Sequence[object], raw_notices)]),
        checked_at=checked,
    )
    validate_incoming(inc)
    return inc


_UNCHECKED_RE = re.compile(r"not_yet_checked")


def merge_status(
    previous: IntegrityState | None, incoming: Incoming | None, run_id: str | None
) -> IntegrityState:
    """The stored state after one load (design §4.1).

    Only a completed check (check status other than `unknown`) can replace `retracted`.
    """
    if incoming is None:
        return previous if previous is not None else UNCHECKED
    if (
        previous is not None
        and previous.status == Status.RETRACTED
        and incoming.check_status == Status.UNKNOWN
    ):
        return IntegrityState(
            status=Status.RETRACTED,
            check_status=Status.UNKNOWN,
            reason=incoming.reason,
            checked_at=incoming.checked_at,
            run_id=run_id,
            notices=previous.notices,
        )
    return IntegrityState(
        status=incoming.effective_status,
        check_status=incoming.check_status,
        reason=incoming.reason,
        checked_at=incoming.checked_at,
        run_id=run_id,
        notices=sort_notices(incoming.notices),
    )

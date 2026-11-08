"""Outcome rows from a verified token and the doctor's answers (doctor-loop design §7.4). Pure."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from janus.contributions.week import report_week
from janus.notes.schemas import AnswerIn
from janus.notes.token import Payload, deletion_hash

# The columns an outcome row may have (privacy: nothing else is stored; P26 checks the table).
OUTCOME_COLUMNS = (
    "id",
    "report_week",
    "region",
    "rule_id",
    "index_key",
    "marker_key",
    "ingredients",
    "event",
    "direction",
    "assessment",
    "action",
    "action_on",
    "form_confirmed",
    "consent_version",
    "deletion_hash",
)


class AnswerError(ValueError):
    """Answers that do not fit the token; carries field paths only."""

    def __init__(self, fields: list[str]) -> None:
        super().__init__("invalid answers")
        self.fields = fields


@dataclass(frozen=True)
class OutcomeRow:
    report_week: dt.date
    region: str
    rule_id: str
    index_key: str
    marker_key: str
    ingredients: tuple[str, str]
    event: str
    direction: str
    assessment: str
    action: str | None
    action_on: str | None
    form_confirmed: bool
    consent_version: str
    deletion_hash: bytes


def outcome_rows(
    payload: Payload, answers: Sequence[AnswerIn], now: dt.datetime
) -> list[OutcomeRow]:
    bad = [f"answers.{i}.ref" for i, a in enumerate(answers) if a.ref >= len(payload.findings)]
    if bad:
        raise AnswerError(bad)
    week = report_week(now)
    rows: list[OutcomeRow] = []
    for a in sorted(answers, key=lambda x: x.ref):
        f = payload.findings[a.ref]
        pair = tuple(sorted((f.index_key, f.marker_key)))
        rows.append(
            OutcomeRow(
                report_week=week,
                region=payload.region,
                rule_id=f"pipc:{f.row}",
                index_key=f.index_key,
                marker_key=f.marker_key,
                ingredients=(pair[0], pair[1]),
                event=f.event,
                direction=f.direction,
                assessment=a.assessment,
                action=a.action,
                action_on=a.action_on,
                form_confirmed=f.form_confirmed,
                consent_version=payload.consent_version,
                deletion_hash=deletion_hash(payload.note_id, a.ref),
            )
        )
    return rows


def deletion_hashes(payload: Payload) -> list[bytes]:
    return [deletion_hash(payload.note_id, r) for r in range(len(payload.findings))]

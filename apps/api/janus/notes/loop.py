"""Outcome loop orchestration (doctor-loop design §7): issue, form, submit, withdraw.

The token carries the finding codes (owner decision 2026-11-08); the server stores only used or
withdrawn note-id hashes until expiry and the outcomes. Nothing of a request is logged.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import psycopg

from janus.cascades import repository as cascade_repository
from janus.cascades.schemas import FindingOut
from janus.db.pool import Database
from janus.notes import qr, render, repository
from janus.notes.glossary import Glossary
from janus.notes.outcomes import deletion_hashes, outcome_rows
from janus.notes.schemas import (
    AnswerIn,
    CascadeNames,
    FormFinding,
    FormOptions,
    FormTexts,
    NamedIngredient,
    OptionOut,
    OutcomeFormOut,
)
from janus.notes.templates import CATALOGUE
from janus.notes.token import (
    MAX_CODES_PER_SIDE,
    Keyring,
    Payload,
    TokenFinding,
    monday_of,
    new_note_id,
)


class NoFindingsError(ValueError):
    pass


class TokenUsedError(RuntimeError):
    pass


class TokenNotUsableError(RuntimeError):
    pass


class LoopUnavailableError(RuntimeError):
    pass


@dataclass
class Issued:
    token: str = ""
    covered: int = 0
    total: int = 0
    expires_on: dt.date | None = None


def token_findings(
    ordered: Sequence[FindingOut], event_keys: Mapping[int, str]
) -> tuple[TokenFinding, ...]:
    out: list[TokenFinding] = []
    for f in ordered:
        row = int(f.rule_id.split(":")[1])
        out.append(
            TokenFinding(
                row=row,
                index_key=f.index.ingredient_key,
                marker_key=f.marker.ingredient_key,
                index_codes=tuple(sorted(set(f.index.matched_codes))[:MAX_CODES_PER_SIDE]),
                marker_codes=tuple(sorted(set(f.marker.matched_codes))[:MAX_CODES_PER_SIDE]),
                event=event_keys[row],
                direction="adverse",
                form_confirmed=f.form_confirmed,
            )
        )
    return tuple(out)


def signer(
    keyring: Keyring,
    *,
    now: dt.datetime,
    language: str,
    region: str,
    consent_version: str,
    event_keys: Mapping[int, str],
    issued: Issued,
) -> Callable[[Sequence[FindingOut]], tuple[int, int]]:
    """The `qr` callback of `compose`: signs the longest fitting prefix into `issued`."""

    def sign(ordered: Sequence[FindingOut]) -> tuple[int, int]:
        if not ordered:
            raise NoFindingsError
        payload = Payload(
            kid=keyring.signing,
            note_id=new_note_id(),
            issue_week=monday_of(now.astimezone(dt.UTC).date()),
            language=language,  # pyright: ignore[reportArgumentType]
            region=region,  # pyright: ignore[reportArgumentType]
            consent_version=consent_version,
            findings=token_findings(ordered, event_keys),
        )
        issued.token, issued.covered = qr.fit_findings(keyring, payload)
        issued.total = len(ordered)
        issued.expires_on = payload.expires_on
        return issued.covered, issued.total

    return sign


def _name(glossary: Glossary, key: str, codes: Sequence[str], lang: str) -> NamedIngredient:
    n = glossary.name(key, lang, None)
    tag = None
    if n.basis == "english_fallback":
        tag = glossary.text("name.not_translated", lang)
    elif n.basis != "glossary":
        tag = glossary.text("name.not_reviewed", lang)
    return NamedIngredient(
        key=key,
        name=n.text if n.text is not None else ", ".join(codes),
        name_basis=n.basis,
        tag=tag,
        atc=list(codes),
    )


def _action_on(glossary: Glossary, code: str, name: str, lang: str) -> OptionOut:
    template = f"outcome.action_on.{code}"
    text, _ = render.fill(CATALOGUE[template], glossary.text(template, lang), {"name": name}, lang)
    return OptionOut(code=code, text=text)


def form(conn: psycopg.Connection, payload: Payload, glossary: Glossary) -> OutcomeFormOut:
    state = repository.token_state(conn, payload.note_hash)
    if state == "used":
        raise TokenUsedError
    if state == "withdrawn":
        raise TokenNotUsableError
    lang = payload.language
    rb = cascade_repository.current_rule_base(conn)
    if rb is None or lang not in glossary.available_languages():
        raise LoopUnavailableError
    english = {r.position: (r.drug_a, r.adverse_event, r.drug_b) for r in rb.rules}
    findings: list[FormFinding] = []
    for ref, f in enumerate(payload.findings):
        names = glossary.cascade(f.row, lang, english[f.row])
        if names is None:
            raise LoopUnavailableError
        index = _name(glossary, f.index_key, f.index_codes, lang)
        marker = _name(glossary, f.marker_key, f.marker_codes, lang)
        findings.append(
            FormFinding(
                ref=ref,
                rule_id=f"pipc:{f.row}",
                cascade=CascadeNames(drug_a=names[0], adverse_event=names[1], drug_b=names[2]),
                index=index,
                marker=marker,
                form_confirmed=f.form_confirmed,
                action_on=[
                    _action_on(glossary, "index", index.name, lang),
                    _action_on(glossary, "marker", marker.name, lang),
                ],
            )
        )

    def options(codes: Sequence[str], prefix: str) -> list[OptionOut]:
        return [OptionOut(code=c, text=glossary.text(f"{prefix}.{c}", lang)) for c in codes]

    t = glossary.text
    return OutcomeFormOut(
        language=lang,
        expires_on=payload.expires_on.isoformat(),
        findings=findings,
        options=FormOptions(
            assessment=options(("confirmed", "not_a_cascade"), "outcome.option"),
            action=options(
                ("dose_changed", "medicine_changed", "stopped", "no_change"), "outcome.option"
            ),
        ),
        texts=FormTexts(
            heading=t("outcome.heading", lang),
            intro=t("outcome.intro", lang),
            stored_fields=t("outcome.stored_fields", lang),
            limits=t("outcome.limits", lang),
            question_assessment=t("outcome.question.assessment", lang),
            question_action=t("outcome.question.action", lang),
            disclaimer=t("disclaimer", lang),
        ),
    )


def submit(db: Database, payload: Payload, answers: Sequence[AnswerIn], now: dt.datetime) -> int:
    rows = outcome_rows(payload, answers, now)  # AnswerError before any write
    result = repository.submit(db, payload.note_hash, payload.expires_on, rows)
    if result is repository.SubmitResult.used:
        raise TokenUsedError
    if result is repository.SubmitResult.withdrawn:
        raise TokenNotUsableError
    return len(rows)


def withdraw(db: Database, payload: Payload, today: dt.date) -> None:
    expired = not today < payload.expires_on
    repository.withdraw(
        db, payload.note_hash, None if expired else payload.expires_on, deletion_hashes(payload)
    )

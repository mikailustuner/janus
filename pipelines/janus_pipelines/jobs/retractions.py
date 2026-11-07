"""`retractions` pipeline: Crossref update notices for every DOI Janus cites (design §5.5,
Req 9). Includes Retraction Watch data (Crossref `updated-by[].source`)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, cast
from urllib.parse import quote

import polars as pl

from janus_pipelines.core.canonical import Json, Row, sha256_bytes
from janus_pipelines.core.http import FetchError, contact_email, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.store import Store
from janus_pipelines.core.validation import Accounting, ExpectedSchema, Field, SchemaReport

WORKS_URL = "https://api.crossref.org/works/"


class Status(StrEnum):
    OK = "ok"
    CORRECTED = "corrected"
    EXPRESSION_OF_CONCERN = "expression_of_concern"
    RETRACTED = "retracted"
    UNKNOWN = "unknown"


SEVERITY = {
    Status.OK: 0,
    Status.CORRECTED: 1,
    Status.EXPRESSION_OF_CONCERN: 2,
    Status.RETRACTED: 3,
}

# Crossref's 12 update types (Crossmark schema). Partial retractions, removals and
# withdrawals count as retracted: a patient-facing finding must not rest on them.
NOTICE_STATUS: dict[str, Status] = {
    "retraction": Status.RETRACTED,
    "partial_retraction": Status.RETRACTED,
    "withdrawal": Status.RETRACTED,
    "removal": Status.RETRACTED,
    "expression_of_concern": Status.EXPRESSION_OF_CONCERN,
    "correction": Status.CORRECTED,
    "corrigendum": Status.CORRECTED,
    "erratum": Status.CORRECTED,
    "addendum": Status.CORRECTED,
    "clarification": Status.CORRECTED,
    "new_version": Status.CORRECTED,
    "new_edition": Status.CORRECTED,
}


def notice_status(notice_type: str) -> Status:
    """Unknown types are shown, not ignored: they count as `corrected` (DP9)."""
    key = notice_type.strip().lower().replace("-", "_").replace(" ", "_")
    return NOTICE_STATUS.get(key, Status.CORRECTED)


def status_from_notices(types: Iterable[str]) -> Status:
    """The most severe notice wins, whatever the order (Req 9.3). No notices → ok."""
    statuses = [notice_status(t) for t in types]
    return max(statuses, key=SEVERITY.__getitem__, default=Status.OK)


def effective(last_completed: Status | None, check: Status) -> Status:
    """A failed check keeps a retracted status (Req 9.5); otherwise this check decides."""
    if check is Status.UNKNOWN and last_completed is Status.RETRACTED:
        return Status.RETRACTED
    return check


_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)
_DOI = re.compile(r"10\.\d{4,9}/\S+")


def normalise_doi(value: str) -> str | None:
    """Lower case, no URL or `doi:` prefix. None if the result is not a DOI. Idempotent."""
    text = value.strip()
    changed = True
    while changed:
        changed = False
        for prefix in _PREFIXES:
            if text.lower().startswith(prefix):
                text = text[len(prefix) :].strip()
                changed = True
    text = text.lower()
    return text if _DOI.fullmatch(text) else None


@dataclass(frozen=True)
class Response:
    status: int | None
    body: bytes | None
    error: str | None = None


@dataclass(frozen=True)
class Previous:
    last_completed: Status | None
    effective: Status


@dataclass(frozen=True)
class Payload:
    dois: tuple[str, ...]
    responses: Mapping[str, Response]
    previous: Mapping[str, Previous] = field(default_factory=dict[str, Previous])
    checked_at: str = ""


def notices_from_message(message: Mapping[str, Any]) -> list[dict[str, Json]]:
    out: list[dict[str, Json]] = []
    for n in cast(list[dict[str, Any]], message.get("updated-by") or []):
        updated = cast(dict[str, Any], n.get("updated") or {})
        date = str(updated.get("date-time", ""))[:10] or None
        out.append(
            {
                "type": str(n.get("type", "")),
                "source": n.get("source"),
                "notice_doi": (str(n["DOI"]).lower() if n.get("DOI") else None),
                "date": date,
            }
        )
    out.sort(key=lambda d: json.dumps(d, sort_keys=True))
    return out


def check_one(response: Response | None) -> tuple[Status, list[dict[str, Json]], str | None]:
    """(check status, notices, reason). Not found or failed → unknown, never ok (Req 9.4)."""
    if response is None or response.error is not None or response.status is None:
        return Status.UNKNOWN, [], "check_failed"
    if response.status == 404:
        return Status.UNKNOWN, [], "not_found"
    if response.status != 200 or response.body is None:
        return Status.UNKNOWN, [], f"http_{response.status}"
    try:
        message = cast(dict[str, Any], json.loads(response.body)["message"])
    except (ValueError, KeyError, TypeError):
        return Status.UNKNOWN, [], "unreadable_response"
    notices = notices_from_message(message)
    return status_from_notices(str(n["type"]) for n in notices), notices, None


RETRACTIONS_SCHEMA = ExpectedSchema(
    version="retractions-1", fields=(Field("doi", frozenset({"str"})),)
)


def _doi_file(doi: str) -> str:
    return sha256_bytes(doi.encode())[:16] + ".json"


class RetractionsJob(Job[Payload]):
    name = "retractions"
    source_id = "crossref"
    schema = RETRACTIONS_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "doi": pl.String(),
        "check_status": pl.String(),
        "effective_status": pl.String(),
        "last_completed_status": pl.String(),
        "reason": pl.String(),
        "notices": pl.List(
            pl.Struct(
                {
                    "type": pl.String(),
                    "source": pl.String(),
                    "notice_doi": pl.String(),
                    "date": pl.String(),
                }
            )
        ),
        "checked_at": pl.String(),
    }

    @staticmethod
    def collect_dois(data_dir: Path) -> list[str]:
        """DOIs of every current evidence source record (Phase 1: emitted by pipelines)."""
        dois: list[str] = []
        root = data_dir / "artifacts"
        if not root.is_dir():
            return dois
        for pipeline_dir in sorted(root.iterdir()):
            if pipeline_dir.name == "retractions":
                continue
            evidence = Store(data_dir, pipeline_dir.name).current_evidence()
            if evidence is not None and evidence.doi:
                dois.append(evidence.doi)
        return dois

    @staticmethod
    def previous_statuses(data_dir: Path) -> dict[str, Previous]:
        store = Store(data_dir, "retractions")
        run_id = store.current_run_id()
        if run_id is None:
            return {}
        out: dict[str, Previous] = {}
        for r in store.read_rows(run_id):
            last = r.get("last_completed_status")
            out[str(r["doi"])] = Previous(
                last_completed=Status(str(last)) if last else None,
                effective=Status(str(r["effective_status"])),
            )
        return out

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        fetcher = make_fetcher(require_contact=True)
        email = contact_email(required=True) or ""
        retrieved = ctx.now()
        dois = tuple(self.collect_dois(ctx.data_dir))
        responses: dict[str, Response] = {}
        for doi in sorted({d for d in (normalise_doi(x) for x in dois) if d}):
            try:
                r = fetcher.get(
                    WORKS_URL + quote(doi, safe="/"),
                    params={"mailto": email},
                    allow_status=frozenset({404}),
                )
                responses[doi] = Response(status=r.status_code, body=r.content)
            except FetchError as exc:
                responses[doi] = Response(status=None, body=None, error=str(exc))
        files = {_doi_file(d): r.body for d, r in responses.items() if r.body is not None}
        digest = sha256_bytes(
            b"".join(d.encode() + b"\0" + (responses[d].body or b"") for d in sorted(responses))
        )
        return RawInput(
            payload=Payload(
                dois=dois,
                responses=responses,
                previous=self.previous_statuses(ctx.data_dir),
                checked_at=retrieved.isoformat(),
            ),
            source_urls=(WORKS_URL,),
            source_sha256=digest,
            retrieved_at=retrieved,
            snapshot_date=retrieved.isoformat(),
            snapshot_date_is_retrieval_time=True,
            raw_files=files,
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        p = raw.payload
        acc = Accounting(input_rows=len(p.dois))
        seen: set[str] = set()
        rows: list[Row] = []
        changes: list[dict[str, Json]] = []
        reasons: list[str] = []
        for value in p.dois:
            doi = normalise_doi(value)
            if doi is None:
                acc.exclude("invalid_doi")
                continue
            if doi in seen:
                acc.exclude("duplicate_doi")
                continue
            seen.add(doi)
            check, notices, reason = check_one(p.responses.get(doi))
            prev = p.previous.get(doi)
            last = prev.last_completed if prev else None
            eff = effective(last, check)
            new_last = check if check is not Status.UNKNOWN else last
            rows.append(
                {
                    "doi": doi,
                    "check_status": check.value,
                    "effective_status": eff.value,
                    "last_completed_status": new_last.value if new_last else None,
                    "reason": reason,
                    "notices": cast(Sequence[Json], notices),
                    "checked_at": p.checked_at or raw.retrieved_at.isoformat(),
                }
            )
            if prev is not None and prev.effective is not eff:
                changes.append({"doi": doi, "from": prev.effective.value, "to": eff.value})
                if prev.effective is Status.RETRACTED:
                    reasons.append(f"{doi}: status changed from retracted to {eff.value}")
        counts: dict[str, int] = {}
        for r in rows:
            key = str(r["effective_status"])
            counts[key] = counts.get(key, 0) + 1
        return ParseResult(
            rows=rows,
            input_rows=acc.input_rows,
            excluded=acc.excluded,
            schema=SchemaReport(),
            metrics={"dois": len(rows), **{f"effective_{k}": v for k, v in sorted(counts.items())}},
            review_reasons=reasons,
            changes=changes,
        )

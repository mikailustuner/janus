"""Types of the evidence-integrity core (evidence-integrity design §3.1, §3.3). Pure.

No I/O, no clock. The pure functions in this package work on an `IntegritySnapshot`.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from janus.resolution.canonical import Json, content_hash


class Status(StrEnum):
    OK = "ok"
    CORRECTED = "corrected"
    EXPRESSION_OF_CONCERN = "expression_of_concern"
    RETRACTED = "retracted"
    UNKNOWN = "unknown"


KINDS: tuple[str, ...] = (
    "dataset",
    "rule",
    "faers_stat",
    "paper",
    "label",
    "ancient",
    "chembl",
    "outcome",
)
STORAGE_VALUES: tuple[str, ...] = (
    "runtime_only",
    "cache",
    "commit",
    "separate_package",
    "cited_only",
)
# Storage rules whose data is fetched or kept by Janus and therefore must declare a cadence.
DATA_STORAGE: frozenset[str] = frozenset({"runtime_only", "cache", "commit"})
STATUS_NAMES: tuple[str, ...] = tuple(s.value for s in Status)
REGIONS: tuple[str, ...] = ("TR", "EU", "US")

ExclusionReason = Literal["retracted", "not_registered", "no_citable_basis"]
EXCLUSION_REASONS: tuple[str, ...] = ("retracted", "not_registered", "no_citable_basis")

ID_RE = re.compile(r"[a-z_]+:[a-z0-9_]+(:[A-Za-z0-9_.-]{1,64})?")
ID_MAX = 100
DOI_RE = re.compile(r"10\.\d{4,9}/\S+")
REASON_RE = re.compile(r"check_failed|not_found|unreadable_response|not_yet_checked|http_\d{3}")
NOTICE_TYPE_RE = re.compile(r"[a-z_]{1,40}")
URL_RE = re.compile(r"https?://\S+")

NOT_YET_CHECKED = "not_yet_checked"


def is_evidence_id(value: object) -> bool:
    return isinstance(value, str) and len(value) <= ID_MAX and ID_RE.fullmatch(value) is not None


@dataclass(frozen=True)
class Notice:
    type: str
    source: str | None
    notice_doi: str | None
    date: dt.date | None


@dataclass(frozen=True)
class IntegrityState:
    status: Status
    check_status: Status
    reason: str | None
    checked_at: dt.date | None
    run_id: str | None
    notices: tuple[Notice, ...] = ()


UNCHECKED = IntegrityState(Status.UNKNOWN, Status.UNKNOWN, NOT_YET_CHECKED, None, None, ())


@dataclass(frozen=True)
class SourceInfo:
    source_id: str
    name: str
    storage: str
    cadence_days: int | None
    license: str | None = None
    region: str | None = None
    url: str | None = None  # first URL in the registry; fallback when a run names none


@dataclass(frozen=True)
class EvidenceRecord:
    id: str
    kind: str
    source_id: str
    source_url: str
    license: str
    region: str | None
    snapshot_date: dt.date
    snapshot_is_retrieval_time: bool
    doi: str | None = None
    locator: str | None = None
    title: str | None = None
    basis: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class IntegritySnapshot:
    """All evidence, statuses and cadences. Immutable; the pure functions read nothing else."""

    records: Mapping[str, EvidenceRecord]
    states: Mapping[str, IntegrityState]
    sources: Mapping[str, SourceInfo]

    def state_of(self, evidence_id: str) -> IntegrityState:
        """State of a DOI-bearing record; a missing state is `unknown / not_yet_checked`."""
        return self.states.get(evidence_id, UNCHECKED)

    def cadence_of(self, evidence_id: str) -> int | None:
        rec = self.records.get(evidence_id)
        if rec is None:
            return None
        src = self.sources.get(rec.source_id)
        return None if src is None else src.cadence_days

    def version(self) -> str:
        """Hash of the canonical content (design §4.7). Independent of the request date."""
        rows: list[Mapping[str, Json]] = []
        for rid in sorted(self.records):
            r = self.records[rid]
            rows.append(
                {
                    "t": "record",
                    "id": r.id,
                    "kind": r.kind,
                    "source_id": r.source_id,
                    "source_url": r.source_url,
                    "license": r.license,
                    "region": r.region,
                    "snapshot_date": r.snapshot_date.isoformat(),
                    "retrieval": r.snapshot_is_retrieval_time,
                    "doi": r.doi,
                    "locator": r.locator,
                    "title": r.title,
                    "basis": sorted(r.basis),
                }
            )
        for sid in sorted(self.states):
            s = self.states[sid]
            rows.append(
                {
                    "t": "state",
                    "id": sid,
                    "status": s.status.value,
                    "check_status": s.check_status.value,
                    "reason": s.reason,
                    "checked_at": s.checked_at.isoformat() if s.checked_at else None,
                    "run_id": s.run_id,
                    "notices": [
                        {
                            "type": n.type,
                            "source": n.source,
                            "notice_doi": n.notice_doi,
                            "date": n.date.isoformat() if n.date else None,
                        }
                        for n in s.notices
                    ],
                }
            )
        for sid in sorted(self.sources):
            c = self.sources[sid]
            rows.append(
                {
                    "t": "source",
                    "id": c.source_id,
                    "name": c.name,
                    "storage": c.storage,
                    "cadence_days": c.cadence_days,
                }
            )
        return content_hash(rows, "integrity-1")

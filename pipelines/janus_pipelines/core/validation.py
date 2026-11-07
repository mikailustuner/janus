"""Expected-schema check, row accounting and the review flag (Req 1.5, 2.1, 2.2). Pure."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction

# Kinds a source value can have. "null" covers None and empty strings are left as "str".
KIND_NULL = "null"


def kind_of(value: object) -> str:
    if value is None:
        return KIND_NULL
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, dt.datetime):
        return "datetime"
    if isinstance(value, dt.date):
        return "date"
    if isinstance(value, (list, tuple)):
        return "list"
    if isinstance(value, Mapping):
        return "object"
    return type(value).__name__


@dataclass(frozen=True)
class Field:
    """A required source field and the kinds it may have."""

    name: str
    kinds: frozenset[str]


@dataclass(frozen=True)
class ExpectedSchema:
    version: str
    fields: tuple[Field, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)


type Observed = Mapping[str, frozenset[str]]


def observe(records: Iterable[Mapping[str, object]], columns: Iterable[str] = ()) -> Observed:
    """Collect, per field, the kinds seen. `columns` adds fields seen without values."""
    seen: dict[str, set[str]] = {c: set() for c in columns}
    for record in records:
        for name, value in record.items():
            seen.setdefault(name, set()).add(kind_of(value))
    return {k: frozenset(v) for k, v in seen.items()}


@dataclass(frozen=True)
class SchemaReport:
    missing: tuple[str, ...] = ()
    wrong_type: tuple[tuple[str, tuple[str, ...]], ...] = ()
    extra: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.missing and not self.wrong_type


class SchemaMismatchError(Exception):
    """The source does not have the expected shape (Req 2.1). Names the fields."""

    def __init__(self, report: SchemaReport) -> None:
        self.report = report
        parts: list[str] = []
        if report.missing:
            parts.append("missing: " + ", ".join(report.missing))
        if report.wrong_type:
            parts.append(
                "wrong type: " + ", ".join(f"{n} ({'/'.join(k)})" for n, k in report.wrong_type)
            )
        super().__init__("schema mismatch; " + "; ".join(parts))


def compare_schema(expected: ExpectedSchema, observed: Observed) -> SchemaReport:
    missing = tuple(f.name for f in expected.fields if f.name not in observed)
    wrong = tuple(
        (f.name, tuple(sorted(observed[f.name] - f.kinds)))
        for f in expected.fields
        if f.name in observed and not observed[f.name] <= f.kinds
    )
    extra = tuple(sorted(set(observed) - set(expected.names)))
    return SchemaReport(missing=missing, wrong_type=wrong, extra=extra)


def check_schema(expected: ExpectedSchema, observed: Observed) -> SchemaReport:
    """Return the report; raise SchemaMismatchError if a field is missing or mistyped."""
    report = compare_schema(expected, observed)
    if not report.ok:
        raise SchemaMismatchError(report)
    return report


class RowAccountingError(Exception):
    """Input rows are not all accounted for (Req 1.5)."""


@dataclass
class Accounting:
    input_rows: int = 0
    excluded: dict[str, int] = field(default_factory=dict[str, int])

    def exclude(self, reason: str, n: int = 1) -> None:
        if not reason:
            raise ValueError("an excluded row needs a reason")
        self.excluded[reason] = self.excluded.get(reason, 0) + n


def check_accounting(input_rows: int, output_rows: int, excluded: Mapping[str, int]) -> None:
    if any(not reason for reason in excluded):
        raise RowAccountingError("excluded rows without a reason")
    if any(n < 0 for n in excluded.values()):
        raise RowAccountingError("negative excluded count")
    total = output_rows + sum(excluded.values())
    if input_rows != total:
        raise RowAccountingError(
            f"input rows {input_rows} != output {output_rows} + excluded {sum(excluded.values())}"
        )


DEFAULT_REVIEW_THRESHOLD = Fraction(1, 10)


def review_needed(previous: int | None, current: int, threshold: Fraction) -> bool:
    """True iff the output row count changed by more than `threshold` of the previous count.

    With no previous artifact the check is skipped (Req 2.2).
    """
    if previous is None:
        return False
    return abs(current - previous) > threshold * previous
